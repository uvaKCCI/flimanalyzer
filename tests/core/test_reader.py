"""Reading data files into tables (flim.core.reader)."""

import pandas as pd
import pytest

from flim.core.reader import ReadSettings, find_files, is_uri, read_file, read_tables


def _write(path, data, sep="\t"):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(data).to_csv(path, sep=sep, index=False)
    return path


def test_files_and_folders(tmp_path):
    a = _write(tmp_path / "a.txt", {"t1": [1.0]})
    b = _write(tmp_path / "sub" / "b.csv", {"t1": [2.0]}, sep=",")
    _write(tmp_path / "sub" / "skip.txt", {"t1": [3.0]})
    (tmp_path / "notes.md").write_text("x")
    files, skipped = find_files(
        [tmp_path, a, tmp_path / "gone.txt"], ReadSettings(exclude=["skip.txt"])
    )
    assert files == [a, b]  # each once, sorted; folders with their subfolders
    assert skipped[str(tmp_path / "gone.txt")] == "not found"
    assert skipped[str(tmp_path / "sub" / "skip.txt")] == "left out"


def test_a_table_per_file_with_source_first(tmp_path):
    a = _write(tmp_path / "x" / "Results.txt", {"t1": [1.0, 2.0], "Cell": ["01", "02"]})
    b = _write(tmp_path / "y" / "Results.txt", {"t1": [3.0], "Cell": ["01"]})
    reading = read_tables([a, b])
    assert list(reading.tables) == ["Results.txt", "Results.txt_1"]  # numbered
    table = reading.tables["Results.txt"]
    assert list(table.columns) == ["Source", "Directory", "File", "t1", "Cell"]  # file order
    assert table["Source"].iloc[0] == a.resolve().as_uri()
    assert (table["Directory"].iloc[0], table["File"].iloc[0]) == (str(a.parent), "Results.txt")
    assert table["Source"].dtype == object  # text
    assert isinstance(table["Cell"].dtype, pd.CategoricalDtype)  # a known category name
    assert list(table["Cell"]) == ["01", "02"]  # leading zeros kept


def test_unreadable_files_are_skipped(tmp_path):
    good = _write(tmp_path / "good.txt", {"t1": [1.0]})
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfe\x00broken")
    reading = read_tables([good, bad])
    assert list(reading.tables) == ["good.txt"] and str(bad) in reading.skipped


def test_a_file_that_cant_be_opened_is_skipped(tmp_path, monkeypatch):
    good = _write(tmp_path / "good.txt", {"t1": [1.0]})
    locked = _write(tmp_path / "locked.txt", {"t1": [2.0]})
    real = pd.read_csv

    def read_csv(path, *args, **kwargs):
        if str(path).endswith("locked.txt"):
            raise PermissionError(13, "Permission denied", str(path))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", read_csv)
    reading = read_tables([good, locked])
    assert list(reading.tables) == ["good.txt"]
    assert reading.skipped[str(locked)] == "locked.txt: can't be opened (Permission denied)"


@pytest.mark.parametrize("encoding", ["no-such-encoding", "base64"])
def test_an_unknown_encoding_is_a_validation_error(encoding):
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match=f"unknown text encoding '{encoding}'"):
        ReadSettings(encoding=encoding)
    assert ReadSettings(encoding="Latin-1").encoding == "Latin-1"


def test_reading_with_an_unknown_encoding_says_so(tmp_path):
    path = _write(tmp_path / "a.txt", {"t1": [1.0]})
    settings = ReadSettings.model_construct(**{**ReadSettings().model_dump(), "encoding": "nope"})
    reading = read_tables([path], settings)
    assert reading.skipped[str(path)] == (
        "a.txt: unknown text encoding 'nope'; for example utf-8 or latin-1"
    )


def test_headers_only(tmp_path):
    path = _write(tmp_path / "a.txt", {"t1": [1.0, 2.0], "t2": [3.0, 4.0]})
    table, _ = read_file(path, nrows=0)
    assert len(table) == 0 and {"t1", "t2", "Source"} <= set(table.columns)


def test_existing_provenance_kept_or_renamed(tmp_path):
    saved = _write(
        tmp_path / "saved.txt",
        {"Source": ["file:///raw/a.txt"], "Directory": ["/raw"], "File": ["a.txt"], "t1": [1.0]},
    )
    table, warnings = read_file(saved)  # existing="keep": a table saved by FLIMAnalyzer
    assert table["Source"].iloc[0] == "file:///raw/a.txt" and warnings == []
    assert table["File"].iloc[0] == "a.txt"
    # a Source column that is not provenance (no URIs) is renamed, with a warning
    other = _write(tmp_path / "other.txt", {"Source": ["lamp 2"], "t1": [1.0]})
    table, warnings = read_file(other)
    assert list(table["Source (before Read)"]) == ["lamp 2"]
    assert table["Source"].iloc[0].startswith("file://") and "renamed" in warnings[0]
    table, _ = read_file(saved, ReadSettings(existing="rename"))
    assert {"Source (before Read)", "Directory (before Read)", "File (before Read)"} <= set(table.columns)


@pytest.mark.parametrize(
    "value, uri",
    [
        ("file:///data/a.txt", True),
        ("https://example.org/x.zarr", True),
        ("s3://bucket/key", True),
        ("C:/data/a.txt", False),  # a Windows drive, not a scheme
        ("lamp 2", False),
        ("file:///a b.txt", False),  # a space: not encoded
        (3, False),
    ],
)
def test_well_formed_uris(value, uri):
    assert is_uri(value) is uri


def test_delimiters(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("t1;t2\n1;2\n")
    table, _ = read_file(path, ReadSettings(delimiter=";"))
    assert list(table[["t1", "t2"]].iloc[0]) == [1, 2]


def test_concatenate_without_the_input_column():
    from flim.configs import ConcatConfig
    from flim.tools.data import Concat

    a, b = pd.DataFrame({"t1": [1.0]}), pd.DataFrame({"t1": [2.0]})
    (table,) = Concat()({"a": a, "b": b}, config=ConcatConfig(add_input=False)).values()
    assert list(table.columns) == ["t1"] and len(table) == 2
