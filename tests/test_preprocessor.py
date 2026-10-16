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


def test_rename_headers(flim_data):
    df = flim_data.rename(columns={"NAD(P)H t1": "Exc1_-Ch1-_t1"})
    proc = pp.defaultpreprocessor()
    preview, changed = proc.rename_headers(df.copy(), preview=True)
    assert changed == {"Exc1_-Ch1-_t1": "trp t1"}
    assert "Exc1_-Ch1-_t1" in preview.columns
    renamed, _ = proc.rename_headers(df)
    assert "trp t1" in renamed.columns


def test_calculate_adds_columns_from_available_inputs(flim_data):
    proc = pp.defaultpreprocessor()
    data, calculated, skipped = proc.calculate(flim_data, inplace=False)
    assert "NAD(P)H tm" not in flim_data.columns
    expected = (
        flim_data["NAD(P)H a1[%]"] * flim_data["NAD(P)H t1"]
        + flim_data["NAD(P)H a2[%]"] * flim_data["NAD(P)H t2"]
    ) / 100
    np.testing.assert_allclose(data["NAD(P)H tm"], expected)
    np.testing.assert_allclose(
        data["FLIRR"], flim_data["NAD(P)H a2[%]"] / flim_data["FAD a1[%]"]
    )
    # no trp columns in the input, so trp calculations are skipped
    assert "trp tm" not in data.columns
    assert any(entry[1][0].startswith("trp") for entry in skipped)
    assert len(calculated) > 0
