import numpy as np
import pytest
import xarray as xr
from affine import Affine
from shapely.geometry import Polygon

from regionmask import Regions
from regionmask.core.mask import (
    _determine_method,
    _inject_mask_docstring,
    _mask_rasterize,
    _mask_rasterize_no_offset,
    _mask_shapely,
    _transform_from_latlon,
)
from regionmask.core.utils import _wrapAngle, create_lon_lat_dataarray_from_bounds

from .utils import (
    dummy_lat,
    dummy_lon,
    dummy_outlines,
    dummy_outlines_poly,
    dummy_region,
    expected_mask_2D,
    expected_mask_3D,
)

# =============================================================================


@pytest.mark.parametrize("func", [_mask_rasterize, _mask_shapely])
def test_mask_func(func):

    # standard
    result = func(dummy_lon, dummy_lat, dummy_outlines_poly, numbers=[0, 1, 2])
    expected = expected_mask_2D()
    assert np.allclose(result, expected, equal_nan=True)

    result = func(dummy_lon, dummy_lat, dummy_outlines_poly, numbers=[0, 1, 2], fill=5)
    expected = expected_mask_2D(fill=5)
    assert np.allclose(result, expected, equal_nan=True)

    result = func(dummy_lon, dummy_lat, dummy_outlines_poly, numbers=[5, 6, 7])
    expected = expected_mask_2D(a=5, b=6)
    assert np.allclose(result, expected, equal_nan=True)


def test_mask_shapely_wrong_number_fill():

    with pytest.raises(ValueError, match="The fill value should not"):
        _mask_shapely(
            dummy_lon, dummy_lat, dummy_outlines_poly, numbers=[0, 1, 2], fill=0
        )

    with pytest.raises(ValueError, match="`numbers` and `coords` must have"):
        _mask_shapely(dummy_lon, dummy_lat, dummy_outlines, numbers=[5])


@pytest.mark.xfail(reason="Not implemented")
@pytest.mark.parametrize("numbers, fill", [[[0, 1], 0], [[0], np.NaN]])
def test_mask_rasterize_wrong_number_fill(numbers, fill):
    # _mask_rasterize does not raise on wrong fill numbers or on missing numbers

    with pytest.raises(ValueError):
        _mask_rasterize(
            dummy_lon, dummy_lat, dummy_outlines_poly, numbers=numbers, fill=fill
        )


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask(method):

    expected = expected_mask_2D()
    result = dummy_region.mask(dummy_lon, dummy_lat, method=method).values
    assert np.allclose(result, expected, equal_nan=True)


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_xarray(method):

    expected = expected_mask_2D()
    result = dummy_region.mask(dummy_lon, dummy_lat, method=method)

    assert isinstance(result, xr.DataArray)
    assert np.allclose(result, expected, equal_nan=True)
    assert np.all(np.equal(result.lat.values, dummy_lat))
    assert np.all(np.equal(result.lon.values, dummy_lon))


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_poly_z_value(method):

    outl1 = Polygon(((0, 0, 1), (0, 1, 1), (1, 1.0, 1), (1, 0, 1)))
    outl2 = Polygon(((0, 1, 1), (0, 2, 1), (1, 2.0, 1), (1, 1, 1)))
    outlines = [outl1, outl2]

    r_z = Regions(outlines)

    expected = expected_mask_2D()
    result = r_z.mask(dummy_lon, dummy_lat, method=method)

    assert isinstance(result, xr.DataArray)
    assert np.allclose(result, expected, equal_nan=True)
    assert np.all(np.equal(result.lat.values, dummy_lat))
    assert np.all(np.equal(result.lon.values, dummy_lon))


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_xarray_name(method):

    msk = dummy_region.mask(dummy_lon, dummy_lat, method=method)

    assert msk.name == "region"


@pytest.mark.parametrize("ndims", [(2, 1), (1, 2), (0, 1)])
def test_mask_unequal_ndim(ndims):

    lon = np.zeros(shape=ndims[0] * (2,))
    lat = np.zeros(shape=ndims[1] * (2,))

    with pytest.raises(ValueError, match="Equal number of dimensions required"):
        dummy_region.mask(lon, lat)


def test_mask_unequal_2D_shapes():

    lon = np.zeros(shape=(2, 3))
    lat = np.zeros(shape=(2, 4))

    with pytest.raises(
        ValueError, match="2D lon and lat coordinates need to have the same shape"
    ):
        dummy_region.mask(lon, lat)


@pytest.mark.parametrize("ndim", [0, 3, 4])
def test_mask_ndim_ne_1_2(ndim):

    lon = np.zeros(shape=ndim * (2,))
    lat = np.zeros(shape=ndim * (2,))

    with pytest.raises(ValueError, match="1D or 2D data required"):
        dummy_region.mask(lon, lat)


@pytest.mark.parametrize("lon_name", ["lon", "longitude"])
@pytest.mark.parametrize("lat_name", ["lat", "latitude"])
@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_obj(lon_name, lat_name, method):

    expected = expected_mask_2D()

    obj = {lon_name: dummy_lon, lat_name: dummy_lat}
    result = dummy_region.mask(
        obj, method=method, lon_name=lon_name, lat_name=lat_name
    ).values

    assert np.allclose(result, expected, equal_nan=True)


@pytest.mark.filterwarnings("ignore:No gridpoint belongs to any region.")
@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_wrap(method):

    # create a test case where the outlines and the lon coordinates
    # are different

    # outline 0..359.9
    outl1 = ((359, 0), (359, 1), (0, 1.0), (0, 0))
    outl2 = ((359, 1), (359, 2), (0, 2.0), (0, 1))
    outlines = [outl1, outl2]

    r = Regions(outlines)

    # lon -180..179.9
    lon = [-1.5, -0.5]
    lat = [0.5, 1.5]

    result = r.mask(lon, lat, method=method, wrap_lon=False).values
    assert np.all(np.isnan(result))

    # this is the wrong wrapping
    result = r.mask(lon, lat, method=method, wrap_lon=180).values
    assert np.all(np.isnan(result))

    expected = expected_mask_2D()

    # determine the wrap automatically
    result = r.mask(lon, lat, method=method, wrap_lon=True).values
    assert np.allclose(result, expected, equal_nan=True)

    # determine the wrap by hand
    result = r.mask(lon, lat, method=method, wrap_lon=360).values
    assert np.allclose(result, expected, equal_nan=True)


@pytest.mark.parametrize("meth", ["mask", "mask_3D"])
def test_wrap_lon_no_error_wrap_lon_false(meth):

    # regions that exceed 360° longitude
    r = Regions([[[-180, 0], [-180, 10], [360, 10], [360, 0]]], numbers=[1])

    # lons that exceed 360° longitude
    lon = np.arange(-175, 360, 2.5)
    lat = np.arange(10, 1, -3)

    mask = getattr(r, meth)(lon, lat, wrap_lon=False)

    # the region index is 1 -> thus this works for 2D and 3D masks
    assert (mask == 1).all()
    np.testing.assert_equal(lon, mask.lon)
    np.testing.assert_equal(lat, mask.lat)

    # -180° is not special cased (no _mask_edgepoints_shapely)
    lon = [-180]
    mask = getattr(r, meth)(lon, lat, wrap_lon=False)
    assert (mask != 1).all()
    np.testing.assert_equal(lon, mask.lon)
    np.testing.assert_equal(lat, mask.lat)


@pytest.mark.parametrize("meth", ["mask", "mask_3D"])
def test_wrap_lon_error_wrap_lon(meth):

    # regions that exceed 360° longitude
    r = Regions([[[-180, 0], [-180, 10], [360, 10], [360, 0]]])

    # lons that exceed 360° longitude
    lon = np.arange(-180, 360, 2.5)
    lat = np.arange(10, 1, -3)

    with pytest.raises(ValueError, match="Set `wrap_lon=False` to skip this check."):
        getattr(r, meth)(lon, lat)


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_autowrap(method):

    expected = expected_mask_2D()

    # create a test case where the outlines and the lon coordinates
    # are different - or the same - should work either way

    # 1. -180..180 regions and -180..180 lon
    lon = [0.5, 1.5]
    lat = [0.5, 1.5]
    result = dummy_region.mask(lon, lat, method=method).values
    assert np.allclose(result, expected, equal_nan=True)

    # 2. -180..180 regions and 0..360 lon
    # outline -180..180
    outl1 = ((-180, 0), (-180, 1), (-1, 1.0), (-1, 0))
    outl2 = ((-180, 1), (-180, 2), (-1, 2.0), (-1, 1))
    outlines = [outl1, outl2]

    r = Regions(outlines)

    # lon -180..179.9
    lon = [358.5, 359.5]
    lat = [0.5, 1.5]

    result = r.mask(lon, lat, method=method).values
    assert np.allclose(result, expected, equal_nan=True)

    # 3. 0..360 regions and -180..180 lon

    # outline 0..359.9
    outl1 = ((359, 0), (359, 1), (0, 1.0), (0, 0))
    outl2 = ((359, 1), (359, 2), (0, 2.0), (0, 1))
    outlines = [outl1, outl2]

    r = Regions(outlines)

    # lon -180..179.9
    lon = [-1.5, -0.5]
    lat = [0.5, 1.5]

    result = r.mask(lon, lat, method=method).values
    assert np.allclose(result, expected, equal_nan=True)

    # 3. 0..360 regions and 0..360 lon

    # lon 0..359.9
    lon = [0.5, 359.5]
    lat = [0.5, 1.5]

    result = r.mask(lon, lat, method=method).values
    assert np.allclose(result, expected, equal_nan=True)


def test_mask_wrong_method():

    msg = "Method must be None or one of 'rasterize' and 'shapely'."
    with pytest.raises(ValueError, match=msg):

        dummy_region.mask(dummy_lon, dummy_lat, method="method")


# ======================================================================

# test 2D array
lon_2D = [[0.5, 1.5], [0.5, 1.5]]
lat_2D = [[0.5, 0.5], [1.5, 1.5]]


def test_mask_2D():

    expected = expected_mask_2D()
    result = dummy_region.mask(lon_2D, lat_2D, method="shapely")

    assert isinstance(result, xr.DataArray)
    assert np.allclose(result, expected, equal_nan=True)

    assert np.all(np.equal(result.lat.values, lat_2D))
    assert np.all(np.equal(result.lon.values, lon_2D))

    assert np.all(np.equal(result.lat_idx.values, [0, 1]))
    assert np.all(np.equal(result.lon_idx.values, [0, 1]))


@pytest.mark.parametrize("lon", [lon_2D, [0, 1, 3], 0])
@pytest.mark.parametrize("lat", [lat_2D, [0, 1, 3], 0])
def test_mask_rasterize_irregular(lon, lat):

    with pytest.raises(ValueError, match="`lat` and `lon` must be equally spaced"):
        dummy_region.mask(lon, lat, method="rasterize")


def test_mask_xarray_in_out_2D():
    # create xarray DataArray with 2D dims

    coords = {
        "lat_1D": [1, 2],
        "lon_1D": [1, 2],
        "lat_2D": (("lat_1D", "lon_1D"), lat_2D),
        "lon_2D": (("lat_1D", "lon_1D"), lon_2D),
    }

    d = np.random.rand(2, 2)

    data = xr.DataArray(d, coords=coords, dims=("lat_1D", "lon_1D"))

    expected = expected_mask_2D()
    result = dummy_region.mask(
        data, lon_name="lon_2D", lat_name="lat_2D", method="shapely"
    )

    assert isinstance(result, xr.DataArray)
    assert np.allclose(result, expected, equal_nan=True)
    assert np.all(np.equal(result.lat_2D.values, lat_2D))
    assert np.all(np.equal(result.lon_2D.values, lon_2D))

    assert np.all(np.equal(result.lat_1D.values, [1, 2]))
    assert np.all(np.equal(result.lon_1D.values, [1, 2]))


@pytest.mark.parametrize("lon_start", [0, 1, -5])
@pytest.mark.parametrize("dlon", [1, 2])
@pytest.mark.parametrize("lat_start", [0, 1, -5])
@pytest.mark.parametrize("dlat", [1, 2])
def test_transform_from_latlon(lon_start, dlon, lat_start, dlat):

    lon = np.arange(lon_start, 20, dlon)
    lat = np.arange(lat_start, 20, dlat)

    r = _transform_from_latlon(lon, lat)

    assert isinstance(r, Affine)

    expected = np.array(
        [dlon, 0, lon_start - dlon / 2, 0, dlat, lat_start - dlat / 2, 0, 0, 1]
    )

    assert np.allclose(np.array(r), expected)


@pytest.mark.parametrize("a, b", [(0, 1), (4, 5)])
@pytest.mark.parametrize("fill", [np.NaN, 3])
def test_rasterize(a, b, fill):

    expected = expected_mask_2D(a=a, b=b, fill=fill)

    result = _mask_rasterize(
        dummy_lon, dummy_lat, dummy_outlines_poly, numbers=[a, b], fill=fill
    )

    assert np.allclose(result, expected, equal_nan=True)


def test_mask_empty():

    with pytest.warns(UserWarning, match="No gridpoint belongs to any region."):
        result = dummy_region.mask([10, 11], [10, 11], method="shapely")

    assert isinstance(result, xr.DataArray)
    assert result.shape == (2, 2)
    assert result.isnull().all()
    assert np.all(np.equal(result.lon.values, [10, 11]))
    assert np.all(np.equal(result.lat.values, [10, 11]))


# =============================================================================
# =============================================================================
# test mask_3D: only basics (same algorithm as mask)


@pytest.mark.parametrize("drop", [True, False])
@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_3D(drop, method):

    expected = expected_mask_3D(drop)
    result = dummy_region.mask_3D(dummy_lon, dummy_lat, drop=drop, method=method)

    assert isinstance(result, xr.DataArray)
    assert result.shape == expected.shape
    assert np.allclose(result, expected, equal_nan=True)
    assert np.all(np.equal(result.lat.values, dummy_lat))
    assert np.all(np.equal(result.lon.values, dummy_lon))

    _dr = dummy_region[[0, 1]] if drop else dummy_region

    assert np.all(np.equal(result.region.values, _dr.numbers))
    assert np.all(result.abbrevs.values == _dr.abbrevs)
    assert np.all(result.names.values == _dr.names)


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_3D_empty(method):

    with pytest.warns(UserWarning, match="No gridpoint belongs to any region."):
        result = dummy_region.mask_3D([10, 11], [10, 11], drop=True, method=method)

    assert isinstance(result, xr.DataArray)
    assert result.shape == (0, 2, 2)
    assert np.all(np.equal(result.lon.values, [10, 11]))
    assert np.all(np.equal(result.lat.values, [10, 11]))


@pytest.mark.parametrize("lon_name", ["lon", "longitude"])
@pytest.mark.parametrize("lat_name", ["lat", "latitude"])
@pytest.mark.parametrize("drop", [True, False])
@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_3D_obj(lon_name, lat_name, drop, method):

    expected = expected_mask_3D(drop)

    obj = {lon_name: dummy_lon, lat_name: dummy_lat}
    result = dummy_region.mask_3D(
        obj, method=method, drop=drop, lon_name=lon_name, lat_name=lat_name
    )

    assert isinstance(result, xr.DataArray)

    assert result.shape == expected.shape
    assert np.allclose(result, expected, equal_nan=True)

    assert np.all(np.equal(result[lat_name].values, dummy_lat))
    assert np.all(np.equal(result[lon_name].values, dummy_lon))

    _dr = dummy_region[[0, 1]] if drop else dummy_region

    assert np.all(np.equal(result.region.values, _dr.numbers))
    assert np.all(result.abbrevs.values == _dr.abbrevs)
    assert np.all(result.names.values == _dr.names)


# =============================================================================
# =============================================================================
# =============================================================================

# create a region such that the edge falls exactly on the lat/ lon coordinates
# ===

# TODO: use func(*(-161, -29, 2),  *(75, 13, -2)) after dropping py27
ds_US_180 = create_lon_lat_dataarray_from_bounds(*(-161, -29, 2) + (75, 13, -2))
ds_US_360 = create_lon_lat_dataarray_from_bounds(
    *(360 + -161, 360 + -29, 2) + (75, 13, -2)
)

outline_180 = np.array([[-100.0, 50.0], [-100.0, 28.0], [-80.0, 28.0], [-80.0, 50.0]])
outline_360 = outline_180 + [360, 0]

outline_hole_180 = np.array(
    [[-86.0, 44.0], [-86.0, 34.0], [-94.0, 34.0], [-94.0, 44.0]]
)
outline_hole_360 = outline_hole_180 + [360, 0]


r_US_180_ccw = Regions([outline_180])  # counter clockwise
r_US_180_cw = Regions([outline_180[::-1]])  # clockwise

r_US_360_ccw = Regions([outline_360])  # counter clockwise
r_US_360_cw = Regions([outline_360[::-1]])  # clockwise

# define poylgon with hole
poly = Polygon(outline_180, [outline_hole_180])
r_US_hole_180_cw = Regions([poly])  # clockwise
poly = Polygon(outline_180, [outline_hole_180[::-1]])
r_US_hole_180_ccw = Regions([poly])  # counter clockwise

poly = Polygon(outline_360, [outline_hole_360])
r_US_hole_360_cw = Regions([poly])  # clockwise
poly = Polygon(outline_360, [outline_hole_360[::-1]])
r_US_hole_360_ccw = Regions([poly])  # counter clockwise


def _expected_rectangle(ds, lon_min, lon_max, lat_min, lat_max, is_360):

    if is_360:
        lon_min += 360
        lon_max += 360

    LON = ds.LON
    LAT = ds.LAT

    expected = (LAT > lat_min) & (LAT <= lat_max)
    return expected & (LON > lon_min) & (LON <= lon_max)


def expected_mask_edge(ds, is_360, number=0, fill=np.NaN):

    expected = _expected_rectangle(ds, -100, -80, 28, 50, is_360)

    # set number and fill value
    expected = expected.where(expected, fill)
    expected = expected.where(expected != 1, number)

    return expected


def expected_mask_interior_and_edge(ds, is_360, number=0, fill=np.NaN):

    expected_outerior = _expected_rectangle(ds, -100, -80, 28, 50, is_360)
    expected_interior = _expected_rectangle(ds, -94, -86, 34, 44, is_360)

    expected = expected_outerior & ~expected_interior

    # set number and fill value
    expected = expected.where(expected, fill)
    expected = expected.where(expected != 1, number)

    return expected


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
@pytest.mark.parametrize(
    "regions", [r_US_180_ccw, r_US_180_cw, r_US_360_ccw, r_US_360_cw]
)
@pytest.mark.parametrize("ds_US, is_360", [(ds_US_180, False), (ds_US_360, True)])
def test_mask_edge(method, regions, ds_US, is_360):

    expected = expected_mask_edge(ds_US, is_360)
    result = regions.mask(ds_US, method=method)

    assert isinstance(result, xr.DataArray)
    assert np.allclose(result, expected, equal_nan=True)
    assert np.all(np.equal(result.lat, ds_US.lat))
    assert np.all(np.equal(result.lon, ds_US.lon))


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
@pytest.mark.parametrize(
    "regions",
    [r_US_hole_180_cw, r_US_hole_180_ccw, r_US_hole_360_cw, r_US_hole_360_ccw],
)
@pytest.mark.parametrize("ds_US, is_360", [(ds_US_180, False), (ds_US_360, True)])
def test_mask_interior_and_edge(method, regions, ds_US, is_360):

    expected = expected_mask_interior_and_edge(ds_US, is_360)
    result = regions.mask(ds_US, method=method)

    assert isinstance(result, xr.DataArray)
    assert np.allclose(result, expected, equal_nan=True)
    assert np.all(np.equal(result.lat.values, ds_US.lat))
    assert np.all(np.equal(result.lon.values, ds_US.lon))


@pytest.mark.xfail(
    raises=AssertionError, reason="https://github.com/mapbox/rasterio/issues/1844"
)
def test_rasterize_edge():

    lon = ds_US_180.lon
    lat = ds_US_180.lat

    expected = expected_mask_edge(ds_US_180, is_360=False)
    result = _mask_rasterize_no_offset(lon, lat, r_US_180_ccw.polygons, numbers=[0])

    assert np.allclose(result, expected, equal_nan=True)


ds_for_45_deg = create_lon_lat_dataarray_from_bounds(*(-0.5, 16, 1) + (10.5, -0.5, -1))

# add a small offset to y to avoid https://github.com/mapbox/rasterio/issues/1844
outline_45_deg = np.array([[0, 10.1], [0, 0.1], [5.1, 0.1], [15.1, 10.1]])

r_45_def_ccw = Regions([outline_45_deg])
r_45_def_cw = Regions([outline_45_deg[::-1]])


@pytest.mark.parametrize("regions", [r_45_def_ccw, r_45_def_cw])
def test_deg45_rasterize_shapely_equal(regions):
    # https://github.com/regionmask/regionmask/issues/80

    shapely = regions.mask(ds_for_45_deg, method="shapely")
    rasterize = regions.mask(ds_for_45_deg, method="rasterize")

    xr.testing.assert_equal(shapely, rasterize)


@pytest.mark.parametrize("regions", [r_45_def_ccw, r_45_def_cw])
def test_deg45_rasterize_offset_equal(regions):
    # https://github.com/regionmask/regionmask/issues/80

    polygons = regions.polygons
    lon = ds_for_45_deg.lon
    lat = ds_for_45_deg.lat

    result_no_offset = _mask_rasterize_no_offset(lon, lat, polygons, numbers=[0])
    result_offset = _mask_rasterize(lon, lat, polygons, numbers=[0])

    assert np.allclose(result_no_offset, result_offset, equal_nan=True)


# =============================================================================

# the whole globe -> can be re-arranged (_mask_rasterize_flip)
ds_GLOB_360 = create_lon_lat_dataarray_from_bounds(*(0, 360, 2) + (75, 13, -2))
# not all lon -> must be masked twice (_mask_rasterize_split)
ds_GLOB_360_part = create_lon_lat_dataarray_from_bounds(*(0, 300, 2) + (75, 13, -2))


@pytest.mark.parametrize("ds_360", [ds_GLOB_360, ds_GLOB_360_part])
@pytest.mark.parametrize("regions_180", [r_US_180_ccw, r_US_180_cw])
def test_rasterize_on_split_lon(ds_360, regions_180):
    # https://github.com/regionmask/regionmask/issues/127

    # using regions_180 and ds_360 lon must be wrapped, making it
    # NOT equally_spaced
    result = regions_180.mask(ds_360, method="rasterize")

    expected = expected_mask_edge(ds_360, is_360=True)
    assert isinstance(result, xr.DataArray)
    assert np.allclose(result, expected, equal_nan=True)
    assert np.all(np.equal(result.lat, expected.lat))
    assert np.all(np.equal(result.lon, expected.lon))

    expected_shapely = regions_180.mask(ds_360, method="shapely")
    xr.testing.assert_equal(result, expected_shapely)


METHODS = {0: "rasterize", 1: "rasterize_flip", 2: "rasterize_split", 3: "shapely"}

equal = np.arange(0.5, 360)
grid_2D = np.arange(10).reshape(2, 5)
un_equal = [0, 1, 2, 4, 5, 6.1]
close_to_equal = equal + np.random.randn(*equal.shape) * 10 ** -6


@pytest.mark.parametrize(
    "lon, m_lon",
    [
        (equal, 0),
        (close_to_equal, 0),
        (_wrapAngle(equal), 1),
        (_wrapAngle(equal)[:-1], 2),
        ([1], 3),
        (grid_2D, 3),
        (un_equal, 3),
    ],
)
@pytest.mark.parametrize(
    "lat, m_lat",
    [(equal, 0), (close_to_equal, 0), ([1], 3), (grid_2D, 3), (un_equal, 3)],
)
def test_determine_method(lon, m_lon, lat, m_lat):

    expected = METHODS[max((m_lon, m_lat))]

    assert _determine_method(lon, lat) == expected


# =============================================================================
# =============================================================================
# =============================================================================

# ensure a global region incudes all gridpoints - also the ones at
# 0°E/ -180°E and -90°N (#GH159)

outline_GLOB_180 = np.array(
    [[-180.0, 90.0], [-180.0, -90.0], [180.0, -90.0], [180.0, 90.0]]
)
outline_GLOB_360 = outline_GLOB_180 + [180, 0]

r_GLOB_180 = Regions([outline_GLOB_180])
r_GLOB_360 = Regions([outline_GLOB_360])

lon180 = np.arange(-180, 180, 10)
lon360 = np.arange(-180, 180, 10)

lat = np.arange(90, -91, -10)


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
@pytest.mark.parametrize("regions", [r_GLOB_180, r_GLOB_360])
@pytest.mark.parametrize("lon", [lon180, lon360])
def test_mask_whole_grid(method, regions, lon):

    mask = regions.mask(lon, lat, method=method)

    assert (mask == 0).all()


def test_inject_mask_docstring():

    result = _inject_mask_docstring(True, True)

    assert "3D" in result
    assert "2D" not in result
    assert "drop :" in result
    assert "geodataframe" in result

    result = _inject_mask_docstring(False, False)

    assert "2D" in result
    assert "3D" not in result
    assert "drop :" not in result
    assert "geodataframe" not in result