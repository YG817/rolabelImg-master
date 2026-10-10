"""Resolve the GDAL/PROJ datasets shipped by the rasterio wheel."""
import os
from pathlib import Path
import sys

base = Path(sys._MEIPASS)
for variable, folder in [('GDAL_DATA', 'gdal_data'), ('PROJ_LIB', 'proj_data'), ('PROJ_DATA', 'proj_data')]:
    path = base / 'rasterio' / folder
    if path.is_dir():
        os.environ[variable] = str(path)
