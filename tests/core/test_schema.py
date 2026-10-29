import numpy as np
import pandas as pd

from flim.core.schema import ColumnInfo, TableSchema


def make_frame():
    return pd.DataFrame(
        {
            "Treatment": pd.Categorical(["Ctrl", "Drug", "Ctrl"]),
            "t1": [1.0, 2.0, 3.0],
            "photons": np.array([10, 20, 30], dtype="int64"),
            "note": ["a", "b", "c"],
        }
    )


def test_from_frame():
    schema = TableSchema.from_frame(make_frame())
    assert schema.names == ["Treatment", "t1", "photons", "note"]
    assert schema.rows == 3 and schema.complete
    assert schema.by_role("category") == ["Treatment"]
    assert schema.by_role("feature") == ["t1", "photons"]
    assert schema.column("note").role == "other"
    assert schema.column("Treatment").levels == ["Ctrl", "Drug"]
    assert schema.column("photons").dtype == "int64"
    assert schema.column("missing") is None


def test_from_frame_lineage():
    source = TableSchema.from_frame(make_frame())
    derived = pd.DataFrame({"t1": [1.0], "rel t1": [0.5]})
    schema = TableSchema.from_frame(derived, rows=False, inputs=(source,))
    assert schema.column("t1").derived_from == ["t1"]
    assert schema.column("rel t1").derived_from == []
    assert schema.rows is None


def test_sample_keeps_columns_types_and_levels():
    schema = TableSchema.from_frame(make_frame())
    sample = schema.sample()
    assert list(sample.columns) == schema.names
    assert TableSchema.from_frame(sample, rows=False) == schema.model_copy(
        update={"rows": None}
    )


def test_sample_contains_every_level():
    schema = TableSchema(
        columns=[
            ColumnInfo(
                name="Day", role="category", dtype="category", levels=list("abcdef")
            ),
            ColumnInfo(name="x", role="feature", dtype="float64"),
        ]
    )
    sample = schema.sample(rows=2)
    assert len(sample) == 6 and set(sample["Day"]) == set("abcdef")


def test_sample_invents_unknown_levels():
    schema = TableSchema(
        columns=[ColumnInfo(name="T", role="category", dtype="category")]
    )
    assert len(schema.sample()["T"].cat.categories) == 2


def test_unknown_and_json():
    assert not TableSchema.unknown().complete
    schema = TableSchema.from_frame(make_frame())
    assert TableSchema.model_validate_json(schema.model_dump_json()) == schema
