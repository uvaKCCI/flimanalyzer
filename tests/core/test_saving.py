"""Save options tied to the data types, and autosave (flim.core.saving)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from flim.core import saving  # noqa: E402
from flim.core.saving import (  # noqa: E402
    AutosaveConfig,
    PlotSaveOptions,
    SaveOptions,
    TableSaveOptions,
    save_value,
)
from flim.core.types import DataType  # noqa: E402
from flim.results import save_results  # noqa: E402


class Note:
    """A value of a plugin's data type."""

    def __init__(self, text):
        self.text = text


@pytest.fixture
def table():
    return pd.DataFrame({"a": [1, 2], "b\nline": [3.0, 4.0]})


@pytest.fixture
def figure():
    fig, ax = plt.subplots(figsize=(2, 1))
    ax.plot([0, 1], [0, 1])
    yield fig
    plt.close(fig)


def test_defaults():
    assert TableSaveOptions().format == "tsv" and TableSaveOptions().extension == ".txt"
    assert PlotSaveOptions().format == "png" and PlotSaveOptions().dpi == 300
    assert PlotSaveOptions(format="svg", dpi=600).dpi is None  # vector: no resolution
    config = AutosaveConfig()
    assert config.formats_for("table") == [TableSaveOptions()]
    assert config.formats_for("file") == []  # no save options: copied as it is


def test_formats_are_validated_by_kind():
    config = AutosaveConfig(
        formats=[
            {"kind": "plot", "format": "png"},
            {"kind": "plot", "format": "svg"},
            {"kind": "plot", "format": "png"},  # exact duplicate: dropped
        ]
    )
    assert [(f.kind, f.format) for f in config.formats] == [("plot", "png"), ("plot", "svg")]
    assert config.formats_for("table") == [TableSaveOptions()]  # not listed: default
    for formats, message in [
        ([{"kind": "movie"}], "unknown kind 'movie'"),
        ([{"format": "png"}], "needs a kind"),
        ([{"kind": "table", "format": "xlsx"}], "format"),
        ([{"kind": "plot", "format": "png"}, {"kind": "plot", "format": "png", "dpi": 72}],
         "listed twice with different options"),
    ]:
        with pytest.raises(ValidationError, match=message):
            AutosaveConfig(formats=formats)


def test_serialized_with_the_options_of_each_kind():
    config = AutosaveConfig(formats=[{"kind": "plot", "format": "png", "dpi": 150}])
    data = config.model_dump(mode="json")
    assert data["formats"] == [{"kind": "plot", "format": "png", "dpi": 150}]
    assert AutosaveConfig.model_validate(data) == config


def test_tables_in_both_formats(tmp_path, table):
    tsv, csv = save_value(
        table, tmp_path / "t", [TableSaveOptions(), TableSaveOptions(format="csv")]
    )
    assert (tsv.name, csv.name) == ("t.txt", "t.csv")
    assert list(pd.read_csv(tsv, sep="\t").columns) == ["a", "b line"]  # one header line
    assert pd.read_csv(csv).shape == (2, 2)  # no row index (#119)


def test_plots_png_at_300_dpi_and_vector_formats(tmp_path, figure):
    from PIL import Image

    files = save_value(
        figure,
        tmp_path / "p",
        [PlotSaveOptions(), PlotSaveOptions(format="svg"), PlotSaveOptions(format="pdf")],
    )
    assert [f.name for f in files] == ["p.png", "p.svg", "p.pdf"]
    with Image.open(files[0]) as image:
        assert image.size == (600, 300)  # 2 x 1 inches at 300 dpi
    assert files[1].read_text().lstrip().startswith("<?xml")
    assert files[2].read_bytes().startswith(b"%PDF")


def test_files_are_copied_and_other_values_not_saved(tmp_path):
    source = tmp_path / "model.pt"
    source.write_bytes(b"weights")
    (copy,) = save_value(source, tmp_path / "copied")
    assert copy.name == "copied.pt" and copy.read_bytes() == b"weights"
    assert save_value({"x": 1}, tmp_path / "d") == []


def test_autosave_uses_the_formats(tmp_path, table, figure):
    formats = AutosaveConfig(
        formats=[{"kind": "table", "format": "csv"}, {"kind": "plot", "format": "svg"}]
    ).formats
    save_results({"Table": table, "Plot": figure, "other": [1]}, tmp_path, "task", formats)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["Plot.svg", "Table.csv", "other", "pickled"]


def test_autosave_default_formats_as_before(tmp_path, table, figure):
    save_results({"Table": table, "Plot": figure}, tmp_path, "task")
    assert {"Table.txt", "Plot.png"} <= {p.name for p in tmp_path.iterdir()}


def test_a_plugin_data_type_brings_its_save_options(tmp_path):
    class TextSaveOptions(SaveOptions):
        kind: str = "text"
        format: str = "md"
        extensions = {"md": ".md"}

    class TextType(DataType):
        pretty_name = "Text"
        pytypes = (f"{__name__}.Note",)  # only this test's values
        kind = "text"
        save_options = TextSaveOptions

        @classmethod
        def save(cls, value, base, options):
            path = Path(f"{base}{options.extension}")
            path.write_text(value.text)
            return path

    config = AutosaveConfig(formats=[{"kind": "text", "format": "md"}])
    assert config.formats_for("text")[0].format == "md"
    (path,) = save_value(Note("# notes"), tmp_path / "n", config.formats)
    assert path.read_text() == "# notes"
    # unregister: other tests must not see the kind (subclasses are kept by weak
    # references)
    import gc

    del TextType, TextSaveOptions, config
    gc.collect()
    assert "text" not in saving.save_options_classes()


def test_header_problems():
    columns = ["a, b", "c\td", "e\nf"]
    assert saving.header_problems(columns, TableSaveOptions(format="csv")) == [
        "a, b: contains a comma",
        "headers of several lines are saved as one line",
    ]
    assert saving.header_problems(columns, TableSaveOptions())[0] == "c\td: contains a tab"


def test_format_fields_round_trip():
    kinds = ["table", "plot"]
    model = saving.formats_model(kinds)
    assert list(model.model_fields) == ["table_formats", "plot_formats", "plot_dpi"]
    values = saving.formats_values(
        model, [PlotSaveOptions(format="svg"), PlotSaveOptions(dpi=150)], kinds
    )
    assert values.table_formats == ["tsv"] and values.plot_formats == ["svg", "png"]
    assert values.plot_dpi == 150
    formats, errors = saving.formats_from_values(values.model_dump(), kinds)
    assert errors == {} and PlotSaveOptions(dpi=150) in formats
    _, errors = saving.formats_from_values({"table_formats": [], "plot_formats": ["png"]}, kinds)
    assert errors == {"table_formats": "Choose at least one format"}
