# -*- mode: python ; coding: utf-8 -*-
# Build on Windows:  BUILD_EXE.bat   →   dist\CHECK_SYSTEM\CHECK_SYSTEM.exe

from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "tools" / "check_app.py")],
    pathex=[str(ROOT), str(ROOT / "src"), str(ROOT / "tools")],
    binaries=[],
    datas=[
        (str(ROOT / "config" / "system.example.json"), "config"),
        (str(ROOT / "config" / "system.schema.json"), "config"),
    ],
    hiddenimports=[
        "dashboard",
        "dashboard_core",
        "platform_store",
        "checktrader",
        "checktrader.config.migrate",
        "pydantic",
        "jsonschema",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CHECK_SYSTEM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app — no black console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CHECK_SYSTEM",
)
