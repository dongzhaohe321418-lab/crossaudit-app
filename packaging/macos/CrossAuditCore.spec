# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parents[1]
datas = collect_data_files("crossaudit.scaffold")
datas += collect_data_files("certifi")
# python-docx computes template paths relative to ``docx.parts.__file__``.
# Modules normally live only inside PyInstaller's PYZ archive, leaving that
# intermediate directory absent even when the template XML files were copied.
# Keep the package tree physical so ``parts/../templates`` resolves in the
# frozen runtime on a clean machine.
datas += collect_data_files("docx", include_py_files=True)
datas.append((str(root / "build" / "macos" / "crossaudit-build.json"), "."))

a = Analysis(
    [str(root / "packaging" / "macos" / "core_entry.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["yaml", "certifi", "docx", "pypdf", "reportlab"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CrossAuditCore",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    argv_emulation=False,
    target_arch="arm64",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CrossAuditCore",
)
