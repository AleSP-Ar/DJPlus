# -*- mode: python ; coding: utf-8 -*-
"""Reproducible Windows x64 onedir build for DJPlus."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).parent
runtime = project_root / "runtime" / "ffmpeg"
runtime_files = (
    "ffmpeg.exe", "CHECKSUM.sha256", "LICENSE.txt", "NOTICE.txt", "SOURCE.txt",
    "VERSION.txt", "BUILD_CONFIGURATION.txt",
)
required = tuple(runtime / name for name in runtime_files)
missing = [str(path.relative_to(project_root)) for path in required if not path.is_file()]
if missing:
    raise SystemExit(f"Faltan recursos obligatorios para empaquetar: {', '.join(missing)}")

datas = [
    (str(path), "runtime/ffmpeg") for path in required
] + [
    (str(project_root / "README.md"), "."),
    (str(project_root / "docs" / "releases" / "V1_0_0_RC1_RELEASE.md"), "docs/releases"),
]
hiddenimports = collect_submodules("app.services") + collect_submodules("app.ui") + [
    "app.database.migrations", "app.database.models", "app.database.unit_of_work",
]

a = Analysis(
    [str(project_root / "app" / "main.py")],
    pathex=[str(project_root)],
    # PyInstaller's official PySide6 hooks collect only Qt plugins reached by
    # the imported Qt modules, avoiding an expensive all-module collection.
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tests", "academy", "database", "models", "services", "ui"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="DJPlus", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="DJPlus")
