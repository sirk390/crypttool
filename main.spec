# -*- mode: python -*-

block_cipher = None


a = Analysis(['main.py'],
           #  pathex=['C:\\Dropbox\\Chris\\projects\\bitcds\\rotate\\GUI'],
             binaries=[],
           # datas=[('rotate.ico', 'GUI')],
             hiddenimports=['wxasync'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['scipy', 'numpy'], # 'tornado', 'matplotlib', 'scipy', 'pandas', 'win32api', 'pywintypes', 'win32com', 'lib2to3', 'pydoc' 'cryptography'
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          

          exclude_binaries=True,
          name='cryptool',
          debug=False,
          strip=False,
          upx=True,
          console=True,
          #icon='rotate.ico'
          )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='CryptTool')
