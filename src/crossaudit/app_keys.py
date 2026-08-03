"""macOS application credentials without ever returning secret values to UI.

The desktop app stores provider keys in the user's login Keychain. The local
HTTP console may ask whether a key exists and may replace or remove one, but it
never receives a stored value back from this module. Environment variables are
populated only inside the app's private core process so the existing provider
boundary stays unchanged.
"""
from __future__ import annotations

import getpass
import os
import shutil
import subprocess
from pathlib import Path

from .errors import ConfigDenial
from .providers.specs import SPECS

APP_SERVICE_PREFIX = "io.crossaudit.app.provider"
PROVIDER_ENVS = {vendor: item.key_env for vendor, item in SPECS.items()}
ROLE_FALLBACKS = {
    "openai": "CROSSAUDIT_AUDITOR_KEY",
    "anthropic": "CROSSAUDIT_GENERATOR_KEY",
}


def env_for_vendor(vendor: str) -> str:
    return PROVIDER_ENVS.get(vendor, f"CROSSAUDIT_{vendor.upper()}_KEY")


def _security() -> str:
    path = shutil.which("security") or "/usr/bin/security"
    if not Path(path).is_file():
        raise ConfigDenial("macOS Keychain is unavailable on this computer")
    return path


def _service(vendor: str) -> str:
    if vendor not in PROVIDER_ENVS:
        raise ConfigDenial(f"unsupported credential provider {vendor!r}")
    return f"{APP_SERVICE_PREFIX}.{vendor}"


def _account() -> str:
    return getpass.getuser() or "crossaudit-user"


def read(vendor: str) -> str:
    """Read one key from Keychain for the private app process only."""
    proc = subprocess.run(
        [_security(), "find-generic-password", "-a", _account(),
         "-s", _service(vendor), "-w"],
        capture_output=True, text=True, timeout=10)
    return proc.stdout.rstrip("\r\n") if proc.returncode == 0 else ""


def write(vendor: str, secret: str) -> None:
    """Replace a Keychain item without placing the secret in argv."""
    secret = str(secret)
    if not secret or len(secret.encode("utf-8")) > 16_384:
        raise ConfigDenial(f"{vendor} API key is empty or unexpectedly large")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in secret):
        raise ConfigDenial(f"{vendor} API key contains control characters")
    proc = subprocess.run(
        [_security(), "add-generic-password", "-U", "-a", _account(),
         "-s", _service(vendor), "-l", f"CrossAudit {vendor.title()} API key",
         "-w"], input=secret + "\n" + secret + "\n",
        capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        raise ConfigDenial(
            f"macOS Keychain refused the {vendor} key: {proc.stderr.strip()[:240]}")
    os.environ[env_for_vendor(vendor)] = secret
    if vendor in ROLE_FALLBACKS:
        os.environ[ROLE_FALLBACKS[vendor]] = secret


def remove(vendor: str) -> None:
    subprocess.run(
        [_security(), "delete-generic-password", "-a", _account(),
         "-s", _service(vendor)], capture_output=True, text=True, timeout=10)
    os.environ.pop(env_for_vendor(vendor), None)
    fallback = ROLE_FALLBACKS.get(vendor)
    if fallback:
        os.environ.pop(fallback, None)


def load_into_environment() -> None:
    """Load explicit env first, then Keychain, then legacy role variables."""
    for vendor, env_name in PROVIDER_ENVS.items():
        secret = os.environ.get(env_name, "").strip()
        if not secret:
            secret = read(vendor).strip()
        if not secret and vendor in ROLE_FALLBACKS:
            secret = os.environ.get(ROLE_FALLBACKS[vendor], "").strip()
        if secret:
            os.environ[env_name] = secret
            if vendor in ROLE_FALLBACKS:
                os.environ[ROLE_FALLBACKS[vendor]] = secret


def status() -> dict:
    return {
        vendor: {"configured": bool(os.environ.get(env_name, "").strip())}
        for vendor, env_name in PROVIDER_ENVS.items()
    }


def apply(payload: object) -> dict:
    """Apply write-only settings from the loopback UI."""
    if not isinstance(payload, dict):
        raise ConfigDenial("settings must be an object")
    for vendor in PROVIDER_ENVS:
        if payload.get(f"remove_{vendor}") is True:
            remove(vendor)
            continue
        value = payload.get(f"{vendor}_key")
        if value not in (None, ""):
            write(vendor, str(value).strip())
    return {"providers": status()}
