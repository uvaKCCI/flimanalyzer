import numpy as np
import pandas as pd
import pytest

from flim.data.concatdata import Concatenator
from flim.data.filterdata import Filter
from flim.data.pivotdata import Pivot
from flim.data.sortdata import Sort
from flim.data.unpivotdata import UnPivot


def run(plugin_cls, input, **params):
    plugin = plugin_cls()
    plugin.configure(input=input, **params)
    return plugin.execute()


def test_sort(flim_data):
    result = run(Sort, {"data": flim_data}, features=["NAD(P)H t1"], ascending=False)
    df = result["Table: Sorted"]
    assert df["NAD(P)H t1"].is_monotonic_decreasing
    assert list(df.index) == list(range(len(flim_data)))


def test_filter_by_category_and_range(flim_data):
    low, high = flim_data["NAD(P)H t1"].quantile([0.25, 0.75])
    rfilter = {
        "name": "NAD(P)H t1",
        "rangelow": low,
        "rangehigh": high,
        "selected": True,
        "dropna": True,
    }
    result = run(
        Filter,
        {"data": flim_data},
        category_filters={"Treatment": ["WT"]},
        range_filters=[rfilter],
    )
    df = result["Table: Filtered"]
    expected = flim_data[
        (flim_data["Treatment"] == "WT") & flim_data["NAD(P)H t1"].between(low, high)
    ]
    assert len(df) == len(expected) > 0
    assert set(df["Treatment"]) == {"WT"}
    assert len(flim_data) == 60  # input untouched


def test_concatenate_vertically(flim_data):
    a, b = flim_data.iloc[:20], flim_data.iloc[20:]
    df = run(Concatenator, {"A": a, "B": b})["Table: Concatenated"]
    assert len(df) == len(flim_data)
    assert df["Source"].dtype == "category"
    assert df["Source"].value_counts().to_dict() == {"A": 20, "B": 40}
    assert df["Treatment"].dtype == "category"
    assert "Old Index" not in df.columns


def test_pivot(flim_data):
    df = run(Pivot, {"data": flim_data}, grouping=["Treatment"], features=["NAD(P)H t1"])[
        "Table: Pivoted"
    ]
    assert {"NAD(P)H t1\nWT", "NAD(P)H t1\nKO"} <= set(df.columns)
    assert len(df) == 30  # one row per FOV/Cell combination


def test_unpivot(flim_data):
    features = ["NAD(P)H t1", "NAD(P)H t2"]
    df = run(UnPivot, {"data": flim_data}, features=features)["Table: Unpivoted"]
    assert len(df) == 2 * len(flim_data)
    # single-line columns: the feature names in "Feature", their values in "Value"
    assert set(df["Feature"]) == set(features)
    assert df["Feature"].dtype == "category"
    np.testing.assert_allclose(
        df.loc[df["Feature"] == "NAD(P)H t1", "Value"].to_numpy(),
        flim_data["NAD(P)H t1"].to_numpy(),
    )


def test_unpivot_strips_feature_prefix_with_regex_characters():
    # pivoted column headers have the form "<feature>\n<category>"
    data = pd.DataFrame(
        {
            "FOV": pd.Categorical(["1", "2"]),
            "Value (a.u.)\nWT": [1.0, 2.0],
            "Value (a.u.)\nKO": [3.0, 4.0],
        }
    )
    df = run(
        UnPivot,
        {"data": data},
        features=["Value (a.u.)\nWT", "Value (a.u.)\nKO"],
        category_name="Treatment",
        feature_name="Value (a.u.)",
    )["Table: Unpivoted"]
    assert set(df["Treatment"]) == {"WT", "KO"}
