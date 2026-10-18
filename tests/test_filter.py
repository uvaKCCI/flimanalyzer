import numpy as np
import pandas as pd
import pytest

from flim.core.filter import RangeFilter


@pytest.fixture
def df():
    return pd.DataFrame({"x": [-1.0, 0.5, np.nan, 2.0, 1.0]})


def test_get_dropped_outside_range_and_nan(df):
    f = RangeFilter("x", rangelow=0, rangehigh=1)
    np.testing.assert_array_equal(f.get_dropped(df), [0, 2, 3])


def test_get_dropped_keeps_nan_without_dropna(df):
    f = RangeFilter("x", rangelow=0, rangehigh=1, dropna=False)
    np.testing.assert_array_equal(f.get_dropped(df), [0, 3])


def test_get_dropped_unknown_column(df):
    assert RangeFilter("y").get_dropped(df) == []


def test_apply_filter_not_inplace(df):
    f = RangeFilter("x", rangelow=0, rangehigh=1)
    filtered = f.apply_filter(df, inplace=False)
    assert list(filtered["x"]) == [0.5, 1.0]
    assert len(df) == 5


def test_params_roundtrip():
    f = RangeFilter("x", rangelow=1, rangehigh=5, selected=True, dropna=False)
    g = RangeFilter(params=f.get_params())
    assert g.get_params() == f.get_params()


def test_set_allowed_swaps_min_max():
    f = RangeFilter("x", rangelow=0, rangehigh=1)
    f.set_allowed(10, -10)
    assert (f.allowedmin, f.allowedmax) == (-10, 10)


def test_range_low_clipped_to_allowed_min():
    f = RangeFilter("x", rangelow=-5, rangehigh=5, allowedmin=0, allowedmax=10)
    assert f.get_rangelow() == 0


@pytest.mark.xfail(strict=True, reason="clip_range assigns self.rangemax instead of self.rangehigh")
def test_range_high_clipped_to_allowed_max():
    f = RangeFilter("x", rangelow=0, rangehigh=50, allowedmin=0, allowedmax=10)
    assert f.get_rangehigh() == 10
