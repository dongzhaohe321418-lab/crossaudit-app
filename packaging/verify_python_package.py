"""Verify the actual wheel in a fresh, isolated Python environment."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath


def inspect_wheel(path: Path, expected_version: str = "") -> dict:
    if not path.is_file() or path.suffix != ".whl":
        raise ValueError(f"wheel not found: {path}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                raise ValueError(f"wheel contains an unsafe path: {name}")
        required = {
            "crossaudit/__init__.py", "crossaudit/app.py",
            "crossaudit/console/page.py",
            "crossaudit/scaffold/templates/GENERAL_AUDIT_RULES.md",
        }
        missing = sorted(required.difference(names))
        if missing:
            raise ValueError(f"wheel is missing runtime files: {', '.join(missing)}")
        if any(name.startswith(("tests/", ".git/", "build/", "dist/")) for name in names):
            raise ValueError("wheel contains development or repository state")
        metadata_name = next((name for name in names if name.endswith(".dist-info/METADATA")), "")
        if not metadata_name:
            raise ValueError("wheel has no package metadata")
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        version = str(metadata.get("Version", ""))
        if expected_version and version != expected_version:
            raise ValueError(
                f"wheel version {version!r} does not match {expected_version!r}")

        # Construct credential markers in parts so this verifier does not flag
        # its own source if it is ever included in a future package.
        markers = [b"sk-" + b"proj-", b"sk-" + b"ant-api", b"gh" + b"o_"]
        for name in names:
            info = archive.getinfo(name)
            if info.file_size > 5 * 1024 * 1024:
                continue
            body = archive.read(name)
            if any(marker in body for marker in markers):
                raise ValueError(f"wheel may contain a credential in {name}")
        return {"version": version, "files": len(names), "bytes": path.stat().st_size}


def installed_smoke(path: Path, expected_version: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="crossaudit-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        env = dict(os.environ)
        env.update({
            "HOME": str(root / "home"), "USERPROFILE": str(root / "home"),
            "CROSSAUDIT_APP_SUPPORT": str(root / "support"),
            "CROSSAUDIT_WORKSPACE_ROOT": str(root / "workspace"),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        })
        (root / "home").mkdir()
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-cache-dir", str(path)],
            env=env, check=True, timeout=180)
        subprocess.run([str(python), "-m", "pip", "check"], env=env,
                       check=True, timeout=30)
        version = subprocess.run(
            [str(python), "-c", "import crossaudit;print(crossaudit.__version__)"],
            env=env, check=True, capture_output=True, text=True, timeout=30
        ).stdout.strip()
        if version != expected_version:
            raise RuntimeError(
                f"installed package version {version!r} does not match {expected_version!r}")
        result = subprocess.run(
            [str(python), "-m", "crossaudit.app", "--self-test"], env=env,
            check=True, capture_output=True, text=True, timeout=60)
        self_test = json.loads(result.stdout)
        if self_test.get("ok") is not True:
            raise RuntimeError("installed runtime self-test failed")
        return {"version": version, "self_test": self_test}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--expected-version", default="")
    args = parser.parse_args(argv)
    package = inspect_wheel(args.wheel.resolve(), args.expected_version)
    installed = installed_smoke(args.wheel.resolve(), package["version"])
    print(json.dumps({"ok": True, "package": package, "installed": installed},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
