from pathlib import Path
from typing import Literal, Optional

import pytest
from pydantic import Field

from flim.configs import (
    LEGACY_TOOL_CONFIGS,
    AERunConfig,
    AETrainConfig,
    CategorizerConfig,
    KMeansConfig,
    LinePlotConfig,
    MergeConfig,
    PCAConfig,
    SeriesAnalysisConfig,
    SortConfig,
)
from flim.core.config import CategoryColumn, Resources, TaskConfig
from flim.core.fields import describe, title_of, visible


def spec(config_class, name):
    return next(s for s in describe(config_class) if s.name == name)


def test_kinds():
    assert spec(KMeansConfig, "n_clusters").kind == "int"
    assert spec(KMeansConfig, "n_clusters").bounds == {"ge": 1}
    assert spec(KMeansConfig, "tolerance").kind == "float"
    assert spec(KMeansConfig, "init").choices == ("k-means++", "random")
    assert spec(KMeansConfig, "cluster_prefix").kind == "text"
    assert spec(SeriesAnalysisConfig, "statistics").kind == "multichoice"
    assert spec(AETrainConfig, "learning_rates").kind == "numbers"
    assert spec(AETrainConfig, "learning_rates").item_type is float
    assert spec(AERunConfig, "model_files").kind == "paths"
    assert spec(CategorizerConfig, "rules").kind == "models"


def test_column_kinds():
    grouping = spec(SortConfig, "grouping")
    assert (grouping.kind, grouping.role) == ("columns", "category")
    features = spec(SortConfig, "features")
    assert (features.kind, features.role, features.allow_all) == (
        "columns",
        "feature",
        True,
    )
    on = spec(MergeConfig, "on")
    assert (on.kind, on.optional) == ("columns", True)


def test_optional_and_union_kinds():
    seed = spec(KMeansConfig, "random_seed")
    assert (seed.kind, seed.optional) == ("int", True)
    components = spec(PCAConfig, "n_components")
    assert (components.kind, components.optional) == ("number", True)
    assert components.bounds == {"ge": 1, "gt": 0, "lt": 1}
    errorbar = spec(LinePlotConfig, "errorbar")
    assert (errorbar.kind, errorbar.choices, errorbar.optional) == (
        "mixed",
        ("sd",),
        True,
    )


def test_hidden_fields():
    names = [s.name for s in visible(describe(SortConfig))]
    assert "classname" not in names and "version" not in names
    # Resources allows only cpu and one thread: nothing to edit, the section is hidden
    assert "resources" not in names
    assert all(s.hidden for s in describe(Resources))
    # the autoencoder tools can choose a device and threads
    assert "resources" in [s.name for s in visible(describe(AETrainConfig))]


def test_titles_and_descriptions():
    class Demo(TaskConfig):
        n_components: int = Field(2, title="Components", description="How many")
        reference: Optional[CategoryColumn] = None
        path: Path = Path(".")
        mode: Literal["a"] = "a"

    assert spec(Demo, "n_components").title == "Components"
    assert spec(Demo, "n_components").description == "How many"
    assert spec(Demo, "reference").kind == "column" and spec(Demo, "reference").optional
    assert spec(Demo, "path").kind == "path"
    assert spec(Demo, "mode").hidden
    assert title_of("n_components") == "N components"


@pytest.mark.parametrize(
    "config_class",
    sorted(set(LEGACY_TOOL_CONFIGS.values()), key=lambda c: c.__name__),
    ids=lambda c: c.__name__,
)
def test_every_config_can_be_described(config_class):
    for s in visible(describe(config_class)):
        assert s.kind != "json" or s.name in (
            "categories",
            "category_filters",
            "per_feature",
        ), s
