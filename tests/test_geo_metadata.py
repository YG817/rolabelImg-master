import warnings
import numpy as np
import pytest
import rasterio
from affine import Affine
from PyQt5.QtWidgets import QApplication
from conftest import wait_until
from geo_metadata import read_center_coordinates, format_dms


def write_geo(path, crs=None, transform=None, width=13, height=7):
    options = dict(driver='GTiff', width=width, height=height, count=1, dtype='uint8')
    if crs:
        options['crs'] = crs
    if transform is not None:
        options['transform'] = transform
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', rasterio.errors.NotGeoreferencedWarning)
        with rasterio.open(path, 'w', **options) as dataset:
            dataset.write(np.zeros((1, height, width), dtype='uint8'))


@pytest.mark.parametrize('value,latitude,expected', [
    (-(17 + 31/60 + 8.12/3600), True, '17 31 8.12S'),
    (18 + 32/60 + 9.67/3600, False, '18 32 9.67E'),
    (-122.5, False, '122 30 0.00W'),
    (12 + 59/60 + 59.999/3600, True, '13 0 0.00N'),
    (0, True, '0 0 0.00N'),
])
def test_dms(value, latitude, expected):
    assert format_dms(value, latitude) == expected


def test_geographic_center_and_copy(window, tmp_path):
    path = tmp_path / 'geo.tif'
    lat = -(17 + 31/60 + 8.12/3600)
    lon = 18 + 32/60 + 9.67/3600
    write_geo(path, 'EPSG:4326', Affine(.001, 0, lon - 6.5*.001, 0, -.001, lat + 3.5*.001))
    window.loadFile(str(path))
    wait_until(lambda: window.filePath == str(path))
    expected = '17 31 8.12S,18 32 9.67E'
    assert window.centerCoordinates.text() == expected
    window.copyCoordinatesButton.click()
    assert QApplication.clipboard().text() == expected
    window.setZoom(200)
    assert window.centerCoordinates.text() == expected
    plain = tmp_path / 'plain.tif'
    write_geo(plain)
    window.loadFile(str(plain))
    assert window.centerCoordinates.text() == ''
    assert not window.copyCoordinatesButton.isEnabled()
    wait_until(lambda: window.filePath == str(plain))
    assert window.centerCoordinates.text() == ''
    assert not window.copyCoordinatesButton.isEnabled()


def test_projected_and_rotated_center(tmp_path):
    path = tmp_path / 'projected.tif'
    write_geo(path, 'EPSG:3857', Affine(10, 0, 1113194.9079327357 - 65, 0, -10, 35))
    assert read_center_coordinates(path)['text'] == '0 0 0.00N,10 0 0.00E'
    write_geo(path, 'EPSG:4326', Affine(.02, .01, 10, .01, -.02, 20), width=10, height=20)
    assert read_center_coordinates(path)['text'] == '19 51 0.00N,10 12 0.00E'


def test_missing_transform_or_crs(tmp_path):
    path = tmp_path / 'missing.tif'
    write_geo(path, 'EPSG:4326')
    assert not read_center_coordinates(path)['text']
    write_geo(path, transform=Affine(.1, 0, 10, 0, -.1, 20))
    assert not read_center_coordinates(path)['text']


def test_gcp_center(tmp_path):
    from rasterio.control import GroundControlPoint
    path = tmp_path / 'gcp.tif'
    write_geo(path, width=10, height=10)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', rasterio.errors.NotGeoreferencedWarning)
        with rasterio.open(path, 'r+') as dataset:
            dataset.gcps = ([GroundControlPoint(row=r, col=c, x=10+c*.1, y=20-r*.1)
                             for r, c in [(0,0), (0,10), (10,0), (10,10)]], rasterio.crs.CRS.from_epsg(4326))
    assert read_center_coordinates(path)['text'] == '19 30 0.00N,10 30 0.00E'
