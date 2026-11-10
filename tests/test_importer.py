import pandas as pd
import pytest

from flim.core import parser
from flim.core.importer import dataimporter


def _write(path, rows, sep="\t"):
    pd.DataFrame(rows).to_csv(path, sep=sep, index=False)
    return path


def test_add_files_from_folders_with_exclusions(tmp_path):
    folder = tmp_path / "run"
    folder.mkdir()
    for name in ("Results_FOV1_WT_1.txt", "Results_FOV2_WT_1.txt", "notes.md", "skip.txt"):
        (folder / name).write_text("a\n1\n")
    imp = dataimporter()
    added, skipped = imp.add_files([str(folder)], exclude=["skip.txt"])
    assert (added, skipped) == (2, 2)  # notes.md: wrong extension, skip.txt: excluded
    assert [p.split("/")[-1] for p in imp.get_files()] == ["Results_FOV1_WT_1.txt", "Results_FOV2_WT_1.txt"]

    assert imp.add_files([str(folder / "Results_FOV1_WT_1.txt")]) == (0, 1)  # already added
    imp.remove_files([imp.get_files()[0]])
    assert len(imp.get_files()) == 1
    imp.remove_allfiles()
    assert imp.get_files() == []
    assert imp.add_files(None) == (None, 0)


def test_import_combines_files_and_parses_file_names(tmp_path):
    a = _write(tmp_path / "Results_FOV1_WT_1.txt", {"NAD(P)H t1": [400.0, 410.0]})
    b = _write(tmp_path / "Results_FOV2_KO_3.txt", {"NAD(P)H t1": [500.0]}, sep=",")
    imp = dataimporter()
    imp.set_parser(parser.fov_treatment_cell_parser())
    imp.set_files([str(a), str(b)])
    data, filenames, headers = imp.import_data(delimiter="\t,")
    assert len(data) == 3 and len(filenames) == 2
    assert {"FOV", "Treatment", "Cell"} <= headers
    assert list(data["Treatment"]) == ["WT", "WT", "KO"]
    assert data["Treatment"].dtype == "category" and data["FOV"].dtype == "category"
    assert list(data["NAD(P)H t1"]) == [400.0, 410.0, 500.0]


def test_combined_category_columns(tmp_path):
    a = _write(tmp_path / "Results_FOV1_WT_1.txt", {"x": [1.0]})
    b = _write(tmp_path / "Results_FOV2_KO_2.txt", {"x": [2.0]})
    imp = dataimporter()
    imp.set_parser(parser.fov_treatment_cell_parser())
    imp.set_column_combos([("FOV", "Treatment")])
    imp.set_files([str(a), str(b)])
    data, _, headers = imp.import_data(delimiter="\t")
    # Fuse Categories' engine, joined with ":" (until 0.6: "-")
    assert "FOV:Treatment" in headers
    assert list(data["FOV:Treatment"]) == ["FOV1:WT", "FOV2:KO"]
    assert isinstance(data["FOV:Treatment"].dtype, pd.CategoricalDtype)


def test_all_pairs_of_text_categories_when_no_combos_are_given(tmp_path):
    a = _write(tmp_path / "Results_FOV1_WT_1.txt", {"x": [1.0]})
    imp = dataimporter()
    imp.set_parser(parser.fov_treatment_cell_parser())
    imp.set_column_combos([])
    imp.set_files([str(a)])
    data, _, headers = imp.import_data(delimiter="\t")
    combos = [h for h in headers if ":" in h]
    assert "FOV:Treatment" in combos and all(len(h.split(":")) == 2 for h in combos)


def _parsed_as_in_0_6(patterns, fname):
    """The filename parser of 0.6, for comparison."""
    import os
    import re

    components = {"Directory": os.path.dirname(fname), "File": os.path.basename(fname)}
    fname = fname.replace("\\", "/")
    for entry in patterns:
        if entry["Use"]:
            match = re.search(entry["Regex"], fname)
            if match is not None:
                components[entry["Category"]] = match.group(1) or "?"
    return components


@pytest.mark.parametrize(
    "name", ["fov_treatment_cell_parser", "celltype_compartment_fov_treatment_cell_parser"]
)
@pytest.mark.parametrize(
    "path",
    [
        "/data/Results_FOV1_WT_7.txt",
        r"C:\data\HeLa\nucleus\Results_FOV2_KO_3.txt",
        "/data/other.csv",
        "/a/b/c/Results__WT_.txt",
    ],
)
def test_filename_patterns_as_in_0_6(name, path):
    p = getattr(parser, name)()
    assert p.parsefilename(path) == _parsed_as_in_0_6(p.get_regexpatterns(), path)


def test_no_readable_files(tmp_path):
    imp = dataimporter()
    imp.files = [str(tmp_path / "gone.txt")]  # deleted after it was added
    data, filenames, headers = imp.import_data()
    assert data is None and filenames == [] and headers == set()
