# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/voice_to_text/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.yaml', '.'),
    ],
    hiddenimports=[
        'voice_to_text',
        'voice_to_text.providers',
        'voice_to_text.providers.base',
        'voice_to_text.providers.groq',
        'voice_to_text.providers.voxtral',
        'voice_to_text.providers.parakeet',
        'voice_to_text.config',
        'groq',
        'sounddevice',
        'numpy',
        'yaml',
        'dotenv',
        'requests',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='voice-to-text',
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