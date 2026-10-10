# Windows one-directory client. The installer packages the complete output folder.
from pathlib import Path
import runpy
from PyInstaller.utils.hooks import collect_all, collect_delvewheel_libs_directory

root = Path(SPECPATH).parent
raster_datas, raster_bins, raster_hidden = collect_all('rasterio')
raster_datas, raster_bins = collect_delvewheel_libs_directory(
    'rasterio', datas=raster_datas, binaries=raster_bins)
datas = raster_datas + [(str(root / 'data'), 'data'),
                       (str(root / 'USER_GUIDE.md'), '.'),
                       (str(root / 'THIRD_PARTY_NOTICES.md'), '.')]
if (root / 'LICENSE').is_file():
    datas.append((str(root / 'LICENSE'), '.'))
a = Analysis([str(root / 'client_entry.py')], pathex=[str(root), str(root / 'libs')],
             binaries=raster_bins, datas=datas, hiddenimports=raster_hidden,
             runtime_hooks=[str(root / 'packaging' / 'rth_gdal.py')],
             excludes=['PyQt4', 'PyQt6', 'PySide2', 'PySide6', 'tkinter', 'pytest'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='roLabelImg',
          debug=False, strip=False, upx=False, console=False,
          version=str(root / 'build' / 'windows-version.txt'), contents_directory='_internal')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='roLabelImg')
