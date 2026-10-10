"""Geographic image-center metadata; never reads the raster pixel array."""
import math
import warnings
from decimal import Decimal, ROUND_HALF_UP


def format_dms(value, latitude):
    limit = 90 if latitude else 180
    if not math.isfinite(value) or abs(value) > limit:
        raise ValueError('经纬度超出有效范围')
    # Round once before splitting so 59.999 seconds carries into minutes/degrees.
    hundredths = int((Decimal(str(abs(value))) * 360000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    degrees, rest = divmod(hundredths, 360000)
    minutes, seconds = divmod(rest, 6000)
    hemisphere = ('S' if value < 0 else 'N') if latitude else ('W' if value < 0 else 'E')
    return '%d %d %.2f%s' % (degrees, minutes, seconds / 100, hemisphere)


def read_center_coordinates(path):
    import rasterio
    from affine import Affine
    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.warp import transform
    try:
        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter('always', NotGeoreferencedWarning)
            with rasterio.open(path) as src:
                # Center of the full raster footprint, not the current viewport.
                gcps, gcp_crs = src.gcps
                if gcps and gcp_crs and src.transform == Affine.identity():
                    from rasterio.transform import GCPTransformer
                    with GCPTransformer(gcps) as transformer:
                        x, y = transformer.xy(src.height / 2, src.width / 2, offset='ul')
                    crs = gcp_crs
                else:
                    if src.crs is None:
                        return dict(text='', message='缺少坐标系，无法计算中心经纬度')
                    src.read_transform()
                    if any(issubclass(n.category, NotGeoreferencedWarning) for n in notices) or (
                            src.rpcs and src.transform == Affine.identity()):
                        return dict(text='', message='缺少可用的地理变换，无法计算中心经纬度')
                    crs = src.crs
                    x, y = src.transform * (src.width / 2, src.height / 2)
                longitude, latitude = transform(crs, 'EPSG:4326', [x], [y])
                lon, lat = longitude[0], latitude[0]
                if math.isfinite(lon) and abs(lon) > 180:
                    lon = (lon + 180) % 360 - 180
                text = format_dms(lat, True) + ',' + format_dms(lon, False)
                return dict(text=text, message='整幅影像中心 · WGS84 · 纬度,经度\n源坐标系：%s' % crs)
    except Exception as exc:
        # Missing or invalid metadata must not prevent the image from opening.
        return dict(text='', message='中心经纬度读取失败：%s' % exc)
