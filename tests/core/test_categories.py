"""Fusing and separating category columns (flim.core.categories)."""

import pandas as pd
import pytest

from flim.core import categories


@pytest.fixture
def table():
    return pd.DataFrame(
        {
            "FOV": pd.Categorical(["2", "1", "2", "1"], categories=["2", "1"]),
            "Cell": pd.Categorical(["1", "1", "2", "2"]),
            "x": [1.0, 2.0, 3.0, 4.0],
        }
    )


def test_fuse_joins_names_and_values(table):
    result = categories.fuse(table, ["FOV", "Cell"])
    (name, fused), = result.columns.items()
    assert name == "FOV:Cell" and list(fused) == ["2:1", "1:1", "2:2", "1:2"]
    # categories: observed combinations, in the order of the source categories
    assert list(fused.categories) == ["2:1", "2:2", "1:1", "1:2"]
    assert result.warnings == []


def test_fuse_name_delimiter_and_missing_values(table):
    table.loc[0, "Cell"] = None
    result = categories.fuse(table, ["FOV", "Cell"], delimiter="/", name="Where")
    fused = result.columns["Where"]
    assert pd.isna(fused[0]) and fused[1] == "1/1"


def test_fuse_warns_when_the_delimiter_occurs(table):
    table["Time"] = pd.Categorical(["0:30", "1:00", "0:30", "1:00"])
    result = categories.fuse(table, ["FOV", "Time"])
    assert any("'0:30'" in w and "ambiguous" in w for w in result.warnings)
    table = table.rename(columns={"Cell": "Cell:ID"})
    assert any("column names" in w for w in categories.fuse(table, ["FOV", "Cell:ID"]).warnings)


def test_separate_reverses_fuse(table):
    fused = pd.DataFrame(categories.fuse(table, ["FOV", "Cell"]).columns)
    result = categories.separate(fused, "FOV:Cell")
    assert list(result.columns) == ["FOV", "Cell"]  # names from the column name
    assert list(result.columns["FOV"]) == list(table["FOV"])
    assert list(result.columns["Cell"]) == list(table["Cell"])


def test_separate_with_several_delimiters_skips_and_parts():
    data = pd.DataFrame({"File": ["/a/Results-ko_01.txt", "/b/Results-wt_02.txt"]})
    result = categories.separate(
        data, "File", delimiters=["-", "_"], names=["", "Treatment", "Cell"],
        part="file name without extension",
    )
    assert list(result.columns) == ["Treatment", "Cell"]  # an empty name: skipped
    assert list(result.columns["Treatment"]) == ["ko", "wt"]
    assert list(result.columns["Cell"]) == ["01", "02"]


def test_separate_warns_and_does_not_shift():
    data = pd.DataFrame({"ID": ["a:1", "b:2:x", "c"]})
    result = categories.separate(data, "ID", names=["Letter", "Number"])
    assert list(result.columns["Letter"])[0] == "a"
    assert pd.isna(result.columns["Letter"][1]) and pd.isna(result.columns["Number"][2])
    assert "2 value(s) have not 2 parts" in result.warnings[0]
    assert "'b:2:x'" in result.warnings[0] and "'c'" in result.warnings[0]


def test_separate_by_patterns_as_the_filename_parser():
    data = pd.DataFrame({"File": [r"C:\data\ctrl\FOV1\cell_3.txt", "/data/dox/FOV2/cell_.txt"]})
    result = categories.separate_by_patterns(
        data, "File",
        [("Treatment", r"/data/(.*?)/"), ("Cell", r"cell_(\d*)"), ("Day", r"day(\d+)")],
    )
    assert list(result.columns["Treatment"]) == ["ctrl", "dox"]  # Windows path as "/"
    assert list(result.columns["Cell"]) == ["3", "?"]  # empty group: "?"
    assert result.columns["Day"].isna().all()
    assert result.warnings == ["Day: the pattern 'day(\\d+)' matched no value"]


@pytest.mark.parametrize("pattern, message", [("(", "not a valid pattern"), ("x", "no group")])
def test_invalid_patterns(pattern, message):
    with pytest.raises(ValueError, match=message):
        categories.separate_by_patterns(pd.DataFrame({"f": ["a"]}), "f", [("A", pattern)])
