import warnings
from functools import partial
from operator import attrgetter

import numpy as np
import pytest

from regionmask import Regions, defined_regions

outl1 = ((0, 0), (0, 1), (1, 1.0), (1, 0))
outl2 = ((0, 1), (0, 2), (1, 2.0), (1, 1))
# no gridpoint in outl3
outl3 = ((0, 2), (0, 3), (1, 3.0), (1, 2))

dummy_outlines = [outl1, outl2, outl3]
dummy_region = Regions(dummy_outlines)
dummy_outlines_poly = dummy_region.polygons

dummy_lon = [0.5, 1.5]
dummy_lat = [0.5, 1.5]
dummy_ll_dict = dict(lon=dummy_lon, lat=dummy_lat)

# in this example the result looks:
# | a fill |
# | b fill |


def expected_mask_2D(a=0, b=1, fill=np.NaN):
    return np.array([[a, fill], [b, fill]])


def expected_mask_3D(drop):

    a = [[True, False], [False, False]]
    b = [[False, False], [True, False]]
    c = [[False, False], [False, False]]

    if drop:
        return np.array([a, b])
    return np.array([a, b, c])


REGIONS = {
    "ar6.all": 58,
    "ar6.land": 46,
    "ar6.ocean": 15,
    "giorgi": 21,
    "srex": 26,
}

REGIONS_DEPRECATED = {
    "_ar6_pre_revisions.all": 55,
    "_ar6_pre_revisions.land": 43,
    "_ar6_pre_revisions.ocean": 12,
    "_ar6_pre_revisions.separate_pacific": 58,
}

REGIONS_REQUIRING_CARTOPY = {
    "natural_earth.countries_110": 177,
    "natural_earth.countries_50": 241,
    "natural_earth.us_states_50": 51,
    "natural_earth.us_states_10": 51,
    "natural_earth.land_110": 1,
    "natural_earth.land_50": 1,
    "natural_earth.land_10": 1,
    "natural_earth.ocean_basins_50": 119,
}


def get_naturalearth_region_or_skip(monkeypatch, region_name):

    from socket import timeout
    from urllib.request import URLError, urlopen

    import cartopy

    # add a timeout to cartopy.io.urlopen else it can run indefinitely
    monkeypatch.setattr(cartopy.io, "urlopen", partial(urlopen, timeout=5))

    try:
        region = attrgetter(region_name)(defined_regions)
    except URLError as e:
        if isinstance(e.reason, timeout):
            warnings.warn("naturalearth donwload timeout - test not run!")
            pytest.skip()
        else:
            raise

    return region