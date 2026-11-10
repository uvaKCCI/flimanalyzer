"""Every tool rejects fewer features and grouping columns than it needs.

The configs declare ``min_features`` and ``min_grouping``; Tool.validate checks them
(dialogs), and the run checks them before the tool runs.
"""

import numpy as np
import pandas as pd
import pytest

import flim.tools  # noqa: F401  (registers the tools)
import flim.workflow  # noqa: F401  (registers the workflows)
from flim.core.registry import tools
from flim.core.schema import TableSchema

# tool -> (min_features, min_grouping), as the former plugins declared them where a
# plugin existed; every registered tool must be listed, so a new tool has to declare
# its requirements
EXPECTED = {
    # data
    "Concatenate": (0, 0),
    "Drop Columns": (0, 0),
    "Filter": (0, 0),
    "Fuse Categories": (0, 2),
    "Merge": (0, 0),
    "Order Categories": (0, 0),
    "Pivot": (1, 0),
    "Rename Columns": (0, 0),
    "Sort": (0, 0),  # sorting by nothing leaves the table as it is
    "Scale": (1, 0),
    "Separate Categories": (0, 0),  # one column, checked by the tool
    "Split": (0, 1),  # 0.6 required a column with a config check, now min_grouping
    "Unpivot": (1, 0),
    # analysis
    "Autoencoder: Augment Data": (1, 1),
    "Autoencoder: Run": (1, 0),  # grouping is hidden: the tool does not group
    "Autoencoder: Train": (2, 0),
    "Categorize Data": (0, 0),  # each rule names its feature
    "Gaussian Mixed Model": (1, 0),
    "K-Means": (1, 0),
    "KS-Statistics": (1, 0),
    "PCA": (2, 0),
    "Random Forest": (1, 0),  # the category to predict is the target field
    "Relative Change": (1, 0),
    "Series Analysis": (2, 0),
    "Summarize": (1, 0),
    # plots
    "Bar Plot": (1, 0),
    "Box Plot": (1, 0),
    "FLIRR Plot": (0, 1),
    "Frequency Histogram": (1, 0),
    "Heatmap": (1, 0),
    "KDE": (1, 0),
    "Line Plot": (1, 0),
    "Pair Plot": (0, 0),  # features in x_vars/y_vars, checked by the tool; 1 works
    "Scatter Plot": (2, 0),
    "Swarm Plot": (1, 0),
    "Violin Plot": (1, 0),
    # workflows
    "Basic FLIRR Analysis": (1, 1),
    "FLIM Data Augmentation Tuning": (2, 0),  # its training steps need 2
    "FLIM Feature Analysis": (1, 0),
}

ALL = [t for ts in tools.by_category().values() for t in ts]


def _table(features=3):
    rng = np.random.default_rng(0)
    data = {"Treatment": pd.Categorical(["Ctrl", "Drug"] * 10)}
    data.update({f"f{i}": rng.random(20) for i in range(features)})
    return pd.DataFrame(data)


def test_every_tool_declares_its_requirements():
    assert sorted(t.name for t in ALL) == sorted(EXPECTED)


@pytest.mark.parametrize("tool", ALL, ids=lambda t: t.name)
def test_requirements_as_in_0_5(tool):
    config = tool.config_class
    assert (config.min_features, config.min_grouping) == EXPECTED[tool.name]


NEEDS_FEATURES = [t for t in ALL if EXPECTED[t.name][0]]
NEEDS_GROUPING = [t for t in ALL if EXPECTED[t.name][1]]


@pytest.mark.parametrize("tool", NEEDS_FEATURES, ids=lambda t: t.name)
def test_too_few_features_is_an_error(tool):
    least = EXPECTED[tool.name][0]
    schema = TableSchema.from_frame(_table())
    few = tool.config_class(features=[f"f{i}" for i in range(least - 1)])
    issues = [i for i in tool.validate(few, [schema]) if i.field == "features"]
    assert issues and issues[0].severity == "error"
    enough = tool.config_class(features=[f"f{i}" for i in range(least)])
    assert not [i for i in tool.validate(enough, [schema]) if i.field == "features"]


@pytest.mark.parametrize("tool", NEEDS_FEATURES, ids=lambda t: t.name)
def test_all_features_are_counted_in_the_table(tool):
    from pydantic import ValidationError

    least = EXPECTED[tool.name][0]
    try:
        config = tool.config_class(features="all")
    except ValidationError:
        pytest.skip("this tool has no 'All features'")
    few = TableSchema.from_frame(_table(features=least - 1))
    assert [i for i in tool.validate(config, [few]) if i.field == "features"]
    enough = TableSchema.from_frame(_table(features=least))
    assert not [i for i in tool.validate(config, [enough]) if i.field == "features"]


@pytest.mark.parametrize("tool", NEEDS_GROUPING, ids=lambda t: t.name)
def test_too_few_grouping_columns_is_an_error(tool):
    schema = TableSchema.from_frame(_table())
    issues = tool.validate(tool.config_class(grouping=[]), [schema])
    assert [i for i in issues if i.field == "grouping" and i.severity == "error"]


@pytest.mark.parametrize(
    "tool", [t for t in NEEDS_FEATURES if t.category != "Workflow"], ids=lambda t: t.name
)
def test_run_refuses_too_few_features(tool):
    # batch mode and workflow steps: a clear error before the tool runs
    with pytest.raises(ValueError, match="select at least"):
        tool().run_task(_table(), config=tool.config_class(features=[]))


def test_summarize_needs_a_statistic():
    # with none, the summary had no columns at all and failed with
    # KeyError: "None of [...] are in the columns"
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        tools.get("Summarize").config_class(aggs=[])
