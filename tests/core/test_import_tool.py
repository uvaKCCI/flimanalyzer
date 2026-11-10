"""The Import tool, the Source column and protected column names."""

import numpy as np
import pandas as pd
import pytest

from flim.configs import ConcatConfig, ImportConfig, SourceFromPathConfig
from flim.core.columns import check_template, make_room
from flim.core.settings import AppSettings
from flim.tools.data import Concat, Import, SourceFromPath, import_steps

PARSER = "fov_treatment_cell_parser"


@pytest.fixture
def data_dir(tmp_path):
    """Raw result files with the channels' column names, 3 rows each."""
    rng = np.random.default_rng(1)
    folder = tmp_path / "data"
    folder.mkdir()
    for treatment in ("WT", "KO"):
        for cell in ("1", "2"):
            a1 = rng.uniform(60, 80, 3)
            pd.DataFrame(
                {
                    "Exc1_-Ch2-_a1[%]": a1,
                    "Exc1_-Ch2-_a2[%]": 100 - a1,
                    "Exc1_-Ch2-_t1": rng.normal(400, 20, 3),
                    "Exc1_-Ch2-_t2": rng.normal(2500, 100, 3),
                    "Exc2_-Ch3-_a1[%]": rng.uniform(20, 40, 3),
                    "Exc3_-Ch4-_x": rng.normal(0, 1, 3),  # dropped
                    " ": [0, 0, 0],  # an empty header: dropped
                }
            ).to_csv(folder / f"Results_FOV1_{treatment}_{cell}.txt", sep="\t", index=False)
    return folder


def _settings():
    settings = AppSettings.default()
    settings.tools.set(Import, ImportConfig(parser=PARSER))
    return settings


def test_import_writes_source_as_text(data_dir):
    (table,) = Import()([data_dir], config=ImportConfig(parser=PARSER)).values()
    assert len(table) == 12
    first = sorted(data_dir.iterdir())[0]
    assert first.resolve().as_uri() in set(table["Source"])
    assert table["Source"].dtype == object  # text: not used by Merge, Pivot, ...
    assert {"Directory", "File", "Treatment", "FOV", "Cell"} <= set(table.columns)
    assert "NAD(P)H t1" not in table.columns  # renaming is a step of its own


def test_import_steps_match_the_import_of_0_6(data_dir):
    """Import, Rename Columns, Drop Columns and Calculate give the table that the
    importer with the preprocessor (FLIMAnalyzer 0.6) gave, plus Source."""
    from flim.core.importer import dataimporter
    from flim.core.parser import instantiate_parser
    from flim.tools.data import import_preprocessor

    settings = _settings()
    new = import_steps([data_dir], settings)
    importer = dataimporter()
    importer.set_files([str(data_dir)])
    importer.set_parser(instantiate_parser(f"flim.core.parser.{PARSER}"))
    importer.set_preprocessor(import_preprocessor(settings))
    old, _, _ = importer.import_data()
    assert set(new.columns) == set(old.columns)
    assert "NAD(P)H tm" in new.columns and "Exc3_-Ch4-_x" not in new.columns
    key = ["Source"]
    pd.testing.assert_frame_equal(
        new.sort_values(key).reset_index(drop=True)[sorted(new.columns)],
        old.sort_values(key).reset_index(drop=True)[sorted(old.columns)],
        check_categorical=False,
    )


def test_import_needs_readable_files(tmp_path):
    with pytest.raises(ValueError, match="no data files found"):
        Import()([tmp_path / "missing"], config=ImportConfig())
    with pytest.raises(ValueError, match="unknown filename parser"):
        Import()([tmp_path], config=ImportConfig(parser="nope"))


def test_import_renames_protected_columns_of_the_files(tmp_path, prefect_harness):
    from flim.core.runner import run_flow

    path = tmp_path / "Results_FOV1_WT_1.txt"
    pd.DataFrame({"Source": ["mine"], "FOV": ["x"], "t1": [1.0]}).to_csv(path, sep="\t", index=False)
    (table,) = Import()([path], config=ImportConfig(parser=PARSER)).values()
    assert list(table["Source (before Import)"]) == ["mine"]
    assert table["Source"].iloc[0].startswith("file://")
    assert list(table["FOV"]) == ["FOV1"]  # a category of the parser replaces it
    config = ImportConfig(parser=PARSER, clash_renames={"Source": "Origin URI"})
    (table,) = Import()([path], config=config).values()
    assert "Origin URI" in table.columns
    run = run_flow("import", lambda: Import()([path], config=ImportConfig(parser=PARSER)))
    (message,) = [a.get("message") for _, a in run.graph.nodes(data=True) if "tool" in a]
    assert "'Source' of 1 file(s) is renamed 'Source (before Import)'" in message
    assert "'FOV' of 1 file(s) is replaced" in message


def test_open_keeps_the_provenance_of_a_saved_table(tmp_path):
    from flim.core.importer import dataimporter

    path = tmp_path / "saved.txt"
    saved = {"Source": ["file:///raw/a.txt"], "Directory": ["/raw"], "File": ["a.txt"], "t1": [1.0]}
    pd.DataFrame(saved).to_csv(path, sep="\t", index=False)
    importer = dataimporter()
    importer.set_files([str(path)])
    table, _, _ = importer.import_data(keep_existing=True)  # as File > Open does
    assert table["Source"].iloc[0] == "file:///raw/a.txt"
    assert table["File"].iloc[0] == "a.txt" and table["Directory"].iloc[0] == "/raw"
    assert "Source (before Import)" not in table.columns


def test_concatenate_renames_an_input_column():
    a = pd.DataFrame({"t1": [1.0, 2.0]})
    b = pd.DataFrame({"t1": [3.0]})
    (first,) = Concat()({"A": a, "B": b}, config=ConcatConfig()).values()
    assert list(first["Input"]) == ["A", "A", "B"]
    # a concatenation of concatenations keeps each level (0.6 failed)
    (again,) = Concat()({"AB": first, "C": b}, config=ConcatConfig()).values()
    assert list(again["Input"]) == ["AB", "AB", "AB", "C"]
    assert list(again["Input (AB)"])[:3] == ["A", "A", "B"]
    assert Concat.validate_data(ConcatConfig(), [first, b])[0].field == "clash_name"


def test_source_from_directory_and_file():
    data = pd.DataFrame(
        {"Directory": [r"D:\KCCI data\9SR", "/data/9SR"], "File": ["a.txt", "b c.txt"], "t1": [1.0, 2.0]}
    )
    (table,) = SourceFromPath()(data, config=SourceFromPathConfig()).values()
    assert list(table["Source"]) == ["file:///D:/KCCI%20data/9SR/a.txt", "file:///data/9SR/b%20c.txt"]
    (table,) = SourceFromPath()(data, config=SourceFromPathConfig(keep_original=False)).values()
    assert list(table.columns) == ["t1", "Source"]
    with_source = data.assign(Source=["x", "y"])
    config = SourceFromPathConfig()
    assert SourceFromPath.proposals(config, [with_source]) == {
        "clash_renames": [{"column": "Source", "new": "Source (before Add Source)"}]
    }
    (table,) = SourceFromPath()(with_source, config=config).values()
    assert list(table["Source (before Add Source)"]) == ["x", "y"]


def test_templates_and_numbering():
    assert make_room(["a", "Source"], ["Source"], "{name} (before {tool})", tool="Import") == {
        "Source": "Source (before Import)"
    }
    # a new name that is taken gets a number
    assert make_room(["Source", "Source (old)"], ["Source"], "{name} (old)") == {"Source": "Source (old)_1"}
    assert make_room(["t1"], ["Source"], "{name} (old)") == {}
    for bad, message in (("{x}", "not one of"), ("before", "needs {name}"), ("{name", "not a valid")):
        with pytest.raises(ValueError, match=message):
            check_template(bad)


def test_short_names_are_checked_by_the_registry():
    from flim.core.registry import ToolRegistry
    from flim.core.tool import Tool
    from flim.configs import SortConfig

    registry = ToolRegistry()

    class One(Tool[SortConfig]):
        name, category, short_name = "Tool One", "Data", "One"

    class Clash(Tool[SortConfig]):
        name, category, short_name = "Tool Two", "Data", "ONE"  # case is ignored

    class Named(Tool[SortConfig]):
        name, category = "one", "Data"  # another tool's short name as name

    class Long(Tool[SortConfig]):
        name, category, short_name = "Tool Three", "Data", "Much too long"

    registry.register(One)
    for cls, message in ((Clash, "both use 'one'"), (Named, "both use 'one'"), (Long, "longer than 10")):
        with pytest.raises(ValueError, match=message):
            registry.register(cls)
    assert One.short() == "One" and Long.short() == "Much too long"
    assert Concat.short() == "Concat" and Import.short() == "Import"
