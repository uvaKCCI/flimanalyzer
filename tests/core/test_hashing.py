"""Content hashes of the data types (flim.core.types, flim.core.hashing)."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flim.core.types import DataType, FileType, ImageType, PlotType, TableType


def _hash(value):
    return DataType.of(value).content_hash(value)


def test_file_hash_is_the_sha256_of_its_bytes(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"FLIRR\n1.0\n")
    assert _hash(path) == hashlib.sha256(b"FLIRR\n1.0\n").hexdigest()
    assert FileType.content_hash(tmp_path) is None  # a folder
    assert FileType.content_hash(tmp_path / "missing.txt") is None


def test_table_hash_follows_columns_dtypes_index_and_values():
    table = pd.DataFrame({"x": [1.0, 2.0], "Treatment": pd.Categorical(["a", "b"])})
    first = _hash(table)
    assert first == TableType.content_hash(table.copy(deep=True))  # the same content
    assert first != _hash(table[["Treatment", "x"]])  # column order
    assert first != _hash(table.rename(columns={"x": "y"}))  # column names
    assert first != _hash(table.astype({"x": "float32"}))  # dtypes
    assert first != _hash(table.set_axis([5, 6]))  # index
    changed = table.copy()
    changed.loc[1, "x"] = 3.0
    assert first != _hash(changed)  # values
    assert _hash(table["x"]) != _hash(table[["x"]])  # a Series is not a table


def test_array_hash_does_not_depend_on_the_array_type_or_chunks():
    da = pytest.importorskip("dask.array")
    image = np.arange(3 * 64 * 64, dtype="uint16").reshape(3, 64, 64)
    first = _hash(image)
    assert first == _hash(da.from_array(image, chunks=(1, 16, 16)))
    assert first == _hash(da.from_array(image, chunks=(3, 64, 7)))
    assert first == ImageType.content_hash(np.asfortranarray(image))  # memory layout
    assert first != _hash(image + 1)
    assert first != _hash(image.astype("uint32"))
    assert first != _hash(image.reshape(64, 3, 64))


def test_types_without_a_hash_return_none():
    assert PlotType.content_hash(object()) is None
    assert DataType.content_hash(Path("x")) is None  # the base type hashes nothing
