"""Collect Files: the files of several inputs in one table."""

from pathlib import Path

import flim.tools  # noqa: F401  (registers the tools)
from flim.configs import CollectFilesConfig
from flim.core.registry import tools


def test_one_row_per_file_with_its_input():
    tool = tools.get("Collect Files")
    results = tool()(
        {"32-0.001-0.0": ["/m/a_epoch0001.model", "/m/a_epoch0002.model"],
         "64-0.001-0.0": Path("/m/b_epoch0001.model"), "failed": None},
        config=CollectFilesConfig(),
    )  # fmt: skip
    (table,) = results.values()
    assert list(table.columns) == ["Input", "File"]
    assert table.values.tolist() == [
        ["32-0.001-0.0", "/m/a_epoch0001.model"],
        ["32-0.001-0.0", "/m/a_epoch0002.model"],
        ["64-0.001-0.0", "/m/b_epoch0001.model"],
    ]


def test_autoencoder_names_without_colons_and_their_former_names():
    for old, new in (("Autoencoder: Run", "Autoencoder Run"),
                     ("Autoencoder: Augment Data", "Autoencoder Augment Data")):  # fmt: skip
        assert tools.get(old).name == new
    training = tools.get("Autoencoder Train Model")
    assert training.category is None  # a step, not in the menus
    assert set(training.extra_tags) == {"Autoencoder Train", "Autoencoder: Train"}
