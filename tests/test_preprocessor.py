import numpy as np
import pytest

from flim.core import preprocessor as pp


def test_tm_weighted_mean_lifetime():
    assert pp.tm(75, 400, 25, 3000) == pytest.approx(1050.0)


def test_nadph_nadh_percent():
    assert pp.nadph_perc(1500) == pytest.approx(0.0)
    assert pp.nadph_perc(4400) == pytest.approx(100.0)
    assert pp.nadh_perc(30.0) == pytest.approx(70.0)


def test_ratio():
    assert pp.ratio(1, 4) == pytest.approx(0.25)
    assert np.isnan(pp.ratio(1, 0))


@pytest.mark.parametrize(
    "func, args",
    [
        (pp.trp_Eperc_1, (1000, 0)),
        (pp.trp_Eperc_2, (1000, 0)),
        (pp.trp_Eperc_3, (1000, 0)),
        (pp.trp_r, (0,)),
        (pp.trp_r, (150,)),  # E% > 100 gives a negative base
    ],
)
def test_division_guards_return_nan(func, args):
    assert np.isnan(func(*args))


def test_trp_r_at_half_efficiency_is_r0():
    assert pp.trp_r(50.0) == pytest.approx(pp.TRP_RZERO)


def test_percentile_ignores_nan():
    p50 = pp.percentile(50)
    assert p50.__name__ == "50 percentile"
    assert p50([1.0, 2.0, 3.0, np.nan]) == pytest.approx(2.0)
