"""Which tools' outputs are lists of parts (`Tool.mappable_output`), and the parts' names
(`Tool.output_prefix`)."""

import pytest

import flim.tools  # noqa: F401  (registers the tools)
from flim.core.registry import tools


def parts(name, **settings):
    tool = tools.get(name)
    config = tool.config_class(**settings)
    return tool.mappable_output(config), [tool.output_prefix(c) for c in tool().map_configs(config)]


def test_summarize_is_mappable_without_single_table_whatever_the_number_of_parts():
    assert parts("Summarize", features=["FLIRR", "FAD a1[%]"], single_table=False) == (
        True, ["FLIRR", "FAD a1[%]"]
    )
    # one feature: still a list, of one part
    assert parts("Summarize", features=["FLIRR"], single_table=False) == (True, ["FLIRR"])
    assert parts("Summarize", features=["FLIRR", "FAD a1[%]"], single_table=True)[0] is False


@pytest.mark.parametrize("name", ["Box Plot", "Swarm Plot", "Violin Plot", "Line Plot", "KDE",
                                  "Frequency Histogram"])  # fmt: skip
def test_plots_are_mappable_without_single_figure(name):
    assert parts(name, features=["FLIRR", "FAD a1[%]"]) == (True, ["FLIRR", "FAD a1[%]"])
    assert parts(name, features=["FLIRR", "FAD a1[%]"], single_figure=True)[0] is False


def test_bar_plot_is_mappable_for_single_bars_only():
    assert parts("Bar Plot", features=["FLIRR"], bar_type="single") == (True, ["FLIRR"])
    assert parts("Bar Plot", features=["FLIRR", "FAD a1[%]"], bar_type="stacked")[0] is False


def test_scatter_plot_parts_are_pairs():
    assert parts("Scatter Plot", features=["a", "b", "c"]) == (True, ["a vs b", "a vs c", "b vs c"])


@pytest.mark.parametrize("name", ["Heatmap", "Pair Plot", "FLIRR Plot"])
def test_one_figure_tools_are_not_mappable(name):
    tool = tools.get(name)
    assert tool.mappable_output(tool.config_class()) is False


def test_autoencoder_parts():
    train = tools.get("Autoencoder Train Model")
    config = train.config_class(batch_sizes=[32, 64], learning_rates=[0.001], weight_decays=[0])
    assert train.mappable_output(config)
    assert [train.output_prefix(c) for c in train().map_configs(config)] == [
        "32-0.001-0.0", "64-0.001-0.0"
    ]
    run = tools.get("Autoencoder: Run")
    config = run.config_class.model_construct(model_files=["/m/model_32_epoch0010.model"])
    assert run.mappable_output(config) and run.output_prefix(config) == "model_32_epoch0010"


def test_other_tools_are_not_mappable_by_default():
    sort = tools.get("Sort")
    config = sort.config_class()
    assert sort.mappable_output(config) is False and sort.output_prefix(config) == ""
