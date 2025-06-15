# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Add project root to path
project_root = Path(SPECPATH)
sys.path.insert(0, str(project_root))

block_cipher = None

a = Analysis(
    ['core/host_core/main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        ('core/comms_core/proto/terminalez/*.py', 'core/comms_core/proto/terminalez/'),
        ('core/comms_core/proto/*.proto', 'core/comms_core/proto/')
    ],
    hiddenimports=[
        'grpc',
        'grpc._cython',
        'grpc._cython.cygrpc',
        'google.protobuf',
        'google.protobuf.json_format',
        'google.protobuf.descriptor',
        'core.comms_core.proto.terminalez.terminalez_pb2',
        'core.comms_core.proto.terminalez.terminalez_pb2_grpc',
        'core.host_core.Controller',
        'core.host_core.graceful_shutdown_handler',
        'core.host_core.UnixPTyTerminal',
        'core.host_core.PlatformTerminalRunner',
        'core.host_core.TerminalFactory',
        'core.host_core.console_handler',
        'core.comms_core.utils.logger',
        'core.comms_core.utils.broadcast',
        'core.comms_core.utils.notify',
        'core.comms_core.utils.rw_lock',
        'core.comms_core.utils.shutdown',
        'core.comms_core.utils.task_registry',
        'core.comms_core.utils.watch',
        'asyncio',
        'subprocess',
        'socket',
        'queue',
        'threading',
        'multiprocessing',
        'ctypes',
        'pty',
        'termios',
        'fcntl',
        'select',
        'signal',
        'os',
        'sys'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'jupyter',
        'IPython',
        'pytest',
        'unittest',
        'test',
        'win32api',
        'win32con',
        'win32process',
        'msvcrt',
        'winsound',
        'winreg'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='tetrax_host',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
