import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from flim.configs import (
    LEGACY_TOOL_CONFIGS,
    AEAugmentConfig,
    AEFeatureConfig,
    AERunConfig,
    AETrainConfig,
    AETuneConfig,
    BarPlotConfig,
    CategorizerConfig,
    CategoryOrderConfig,
    ConcatConfig,
    FilterConfig,
    HistogramConfig,
    KMeansConfig,
    KSStatsConfig,
    LinePlotConfig,
    MergeConfig,
    PairPlotConfig,
    PCAConfig,
    RandomForestConfig,
    SeriesAnalysisConfig,
    SortConfig,
    SummaryConfig,
)
from flim.configs.analysis import CategoryRule
from flim.configs.data import RangeFilterSpec
from flim.configs.plot import HistogramRange
from flim.core.config import TaskConfig, fixed_value
from flim.core.registry import tools

CONFIGS = sorted(set(LEGACY_TOOL_CONFIGS.values()), key=lambda c: c.__name__)

# configs with values other than the defaults, all representable as legacy params
CHANGED = [
    CategoryOrderConfig(categories={"Treatment": ["Ctrl", "Drug"]}),
    ConcatConfig(mode="horizontal", numbers_only=True),
    FilterConfig(
        category_filters={"Cell": ["1", "2"]},
        range_filters=[RangeFilterSpec(column="FLIRR", low=0, high=2, selected=True)],
    ),
    MergeConfig(how="outer"),
    SortConfig(features=["FLIRR"], ascending=False),
    SummaryConfig(aggs=["mean", "sem"], single_table=False, prefix="run1"),
    KSStatsConfig(grouping=["Treatment"], alpha=0.01),
    SeriesAnalysisConfig(statistics={"delta", "series_mean"}, merge_input=True),
    PCAConfig(n_components=3, keep_original=True),
    KMeansConfig(n_clusters=4, algorithm="elkan", features="all"),
    RandomForestConfig(target="Treatment", test_size=0.2),
    CategorizerConfig(
        rules=[CategoryRule(value="low", feature="FLIRR", min=0, max=1)],
        merge_input=False,
    ),
    AETrainConfig(
        epochs=3, learning_rates=[1e-3, 1e-4], resources={"preferred_device": "cpu"}
    ),
    AERunConfig(model_files=[Path("a.pth"), Path("b.pth")]),
    AEAugmentConfig(model_files=[Path("a.pth")], sets=3, snr_db=10),
    BarPlotConfig(orientation="horizontal", error_type="s.e.m.", legend=False),
    LinePlotConfig(errorbar="sd", err_style="band"),
    HistogramConfig(
        bins=50,
        table=True,
        per_feature={"FLIRR": HistogramRange(min=0, max=2.4, bins=81)},
    ),
    PairPlotConfig(
        features=["a", "b", "c"],
        x_vars=["a"],
        diagonal="KDE",
        points={"mode": "sample", "samples": 10},
    ),
    AETuneConfig(
        features=["FAD t1"],
        timeseries="Day",
        resources={"preferred_device": "cuda"},
        training=AETrainConfig(
            epochs=2,
            architecture="AE Simulator 1-6",
            rescale=True,
            checkpoint_interval=2,
        ),
        augment=AEAugmentConfig(sets=7),
    ),
    AEFeatureConfig(grouping=["Treatment", "Cell"], control_group="Untreated"),
]


@pytest.mark.parametrize("config_class", CONFIGS, ids=lambda c: c.__name__)
def test_defaults_are_valid_and_survive_json(config_class):
    cfg = config_class()
    assert isinstance(cfg, TaskConfig)
    assert config_class.model_validate_json(cfg.model_dump_json()) == cfg


@pytest.mark.parametrize("config_class", CONFIGS, ids=lambda c: c.__name__)
def test_default_legacy_round_trip(config_class, caplog):
    with caplog.at_level(logging.WARNING):
        cfg = config_class.from_legacy_params(config_class().to_legacy_params())
    assert cfg == config_class()
    assert not caplog.records  # to_legacy_params writes only known keys


@pytest.mark.parametrize("cfg", CHANGED, ids=lambda c: type(c).__name__)
def test_legacy_round_trip(cfg):
    assert type(cfg).from_legacy_params(cfg.to_legacy_params()) == cfg
    assert type(cfg).model_validate_json(cfg.model_dump_json()) == cfg


def test_shared_legacy_params():
    params = {
        "grouping": ["Treatment"],
        "features": "all_features",
        "prefix": "x",
        "input": {},
        "autosave": True,
        "working_dir": "/tmp",
        "saveconfig": False,
        "config_file": "c.json",
    }
    cfg = SortConfig.from_legacy_params(params)
    assert cfg.features == "all" and cfg.grouping == ["Treatment"] and cfg.prefix == "x"
    assert cfg.to_legacy_params()["features"] == "all_features"
    assert "autosave" not in cfg.to_legacy_params()


def test_unknown_legacy_params_are_logged(caplog):
    with caplog.at_level(logging.WARNING):
        cfg = SortConfig.from_legacy_params({"ascending": False, "bogus": 1})
    assert cfg.ascending is False
    assert "bogus" in caplog.text


def test_dropped_legacy_params_are_not_logged(caplog):
    with caplog.at_level(logging.WARNING):
        FilterConfig.from_legacy_params({"use": True, "inplace": False})
        LinePlotConfig.from_legacy_params({"x": "", "display": ["auto", "auto"]})
    assert not caplog.records


def test_legacy_params_are_not_modified():
    params = {"type": True, "numbers_only": False}
    ConcatConfig.from_legacy_params(params)
    assert params == {"type": True, "numbers_only": False}


# --- conversions that need more than a rename ---


def test_concat_mode():
    assert ConcatConfig.from_legacy_params({"type": True}).mode == "horizontal"
    assert ConcatConfig.from_legacy_params({"type": False}).mode == "vertical"
    assert ConcatConfig(mode="horizontal").to_legacy_params()["type"] is True


def test_category_order():
    params = {
        "categories": {"T": {"values": ["b", "a"], "sort": "custom"}},
        "inplace": False,
    }
    cfg = CategoryOrderConfig.from_legacy_params(params)
    assert cfg.categories == {"T": ["b", "a"]}
    assert cfg.to_legacy_params()["categories"] == {
        "T": {"values": ["b", "a"], "sort": "custom"}
    }


def test_range_filter():
    legacy = {
        "name": "FLIRR",
        "rangelow": 0.1,
        "rangehigh": 2,
        "allowedmin": None,
        "allowedmax": None,
        "selected": True,
        "dropna": True,
    }
    cfg = FilterConfig.from_legacy_params({"range_filters": [legacy]})
    assert cfg.range_filters[0].column == "FLIRR" and cfg.range_filters[0].low == 0.1
    assert cfg.to_legacy_params()["range_filters"] == [legacy]
    with pytest.raises(ValidationError):
        RangeFilterSpec(column="x", low=2, high=1)


def test_merge_empty_how_means_inner():
    assert MergeConfig.from_legacy_params({"how": ""}).how == "inner"
    with pytest.raises(ValidationError):
        MergeConfig(how="cross")


def test_kmeans_old_algorithm_names():
    assert KMeansConfig.from_legacy_params({"algorithm": "auto"}).algorithm == "lloyd"
    assert KMeansConfig.from_legacy_params({"algorithm": "full"}).algorithm == "lloyd"


def test_series_statistics():
    cfg = SeriesAnalysisConfig.from_legacy_params(
        {"series_min": False, "series_mean": True}
    )
    assert "series_min" not in cfg.statistics and "series_mean" in cfg.statistics
    assert "delta" in cfg.statistics  # missing keys keep their defaults
    legacy = cfg.to_legacy_params()
    assert legacy["series_min"] is False and legacy["series_mean"] is True


def test_random_forest_target():
    assert RandomForestConfig.from_legacy_params({"classifier": ""}).target is None
    assert RandomForestConfig(target="T").to_legacy_params()["classifier"] == "T"


def test_categorizer_rules():
    cfg = CategorizerConfig()
    assert [r.value for r in cfg.rules] == ["negative", "neutral", "positive"]
    with pytest.raises(ValidationError):
        CategoryRule(value="x", feature="f", min=1, max=1)
    with pytest.raises(ValidationError, match="overlap"):
        CategorizerConfig(
            rules=[
                CategoryRule(value="a", feature="f", min=0, max=2),
                CategoryRule(value="b", feature="f", min=1, max=3),
            ]
        )
    # touching ranges and ranges of different features are fine
    CategorizerConfig(
        rules=[
            CategoryRule(value="a", feature="f", min=0, max=1),
            CategoryRule(value="b", feature="f", min=1, max=2),
            CategoryRule(value="c", feature="g", min=0, max=2),
        ]
    )


def test_histogram_skips_unread_list_settings():
    params = {
        "featuresettings": {
            "FLIRR": [0, 2.4, 81, ["Treatment"]],  # never read by the plugin
            "FAD t1": {"min": 0, "max": 4000, "bins": 81},
            "FAD t2": {"min": 5, "max": 5, "bins": 30},  # invalid range
        }
    }
    cfg = HistogramConfig.from_legacy_params(params)
    assert cfg.per_feature == {"FAD t1": HistogramRange(min=0, max=4000, bins=81)}


def test_pair_plot():
    cfg = PairPlotConfig.from_legacy_params(
        {"plotting": "sample", "samples": 500, "random_seed": 3}
    )
    assert cfg.points.mode == "sample" and cfg.points.samples == 500
    assert cfg.points.random_seed == 3
    with pytest.raises(ValidationError):
        PairPlotConfig(features=["a"], x_vars=["b"])
    with pytest.raises(ValidationError):
        PairPlotConfig(points={"samples": 0})


def test_line_plot_errorbar():
    assert LinePlotConfig.from_legacy_params({"ci": None}).errorbar is None
    assert LinePlotConfig.from_legacy_params({"ci": 68}).errorbar == 68
    with pytest.raises(ValidationError):
        LinePlotConfig(errorbar=100)


def test_bar_plot_old_sem_spelling():
    assert (
        BarPlotConfig.from_legacy_params({"error_type": "s.e.m"}).error_type == "s.e.m."
    )


def test_field_constraints():
    with pytest.raises(ValidationError):
        KSStatsConfig(alpha=0.2)  # not in the critical value table
    with pytest.raises(ValidationError):
        AETrainConfig(train_size=1.0)
    with pytest.raises(ValidationError):
        AETrainConfig(epochs=0)
    with pytest.raises(ValidationError):
        AETrainConfig(learning_rates=[])
    with pytest.raises(ValidationError):
        SummaryConfig(aggs=["mode"])
    assert PCAConfig(n_components=None).n_components is None
    with pytest.raises(ValidationError):
        PCAConfig(n_components=0)


# --- autoencoders ---


def test_autoencoder_device():
    cfg = AETrainConfig.from_legacy_params({"device": "mps", "epoches": 5})
    assert cfg.resources.preferred_device == "mps" and cfg.epochs == 5
    assert cfg.to_legacy_params()["device"] == "mps"
    assert fixed_value(type(cfg.resources), "preferred_device") == (False, None)
    with pytest.raises(ValidationError):
        AETrainConfig(resources={"preferred_device": "tpu"})


@pytest.mark.parametrize(
    "modelfile, expected", [("", []), ("m.pth", ["m.pth"]), (["a", "b"], ["a", "b"])]
)
def test_model_files(modelfile, expected):
    cfg = AERunConfig.from_legacy_params({"modelfile": modelfile})
    assert cfg.model_files == [Path(p) for p in expected]
    assert AERunConfig().to_legacy_params()["modelfile"] == ""


def test_ae_tune_workflow_legacy():
    cfg = AETuneConfig.from_legacy_params(
        {"sets": 2, "epoches": 9, "device": "cpu", "grouping": ["T"], "features": ["f"]}
    )
    assert cfg.augment.sets == 2
    assert cfg.training.epochs == 9
    assert cfg.grouping == ["T"] and cfg.features == ["f"]
    # workflow defaults, not those of the tool
    assert cfg.training.architecture == "AE Simulator 1-6" and cfg.training.rescale
    assert cfg.resources.preferred_device == "cpu"


def test_ae_feature_workflow_legacy():
    cfg = AEFeatureConfig.from_legacy_params(
        {"ctrl_group": "Untreated", "device": "cuda", "timeseries": "Day"}
    )
    assert cfg.control_group == "Untreated" and cfg.timeseries == "Day"
    assert cfg.training.architecture == "AE Dimensionality Reduction 2-10"
    assert cfg.to_legacy_params()["ctrl_group"] == "Untreated"
    assert cfg.to_legacy_params()["device"] == "cuda"


# --- workflows: fields the workflow sets in its steps ---


def test_workflow_shares_fields_with_steps():
    cfg = AETuneConfig(
        grouping=["T"],
        features=["f"],
        timeseries="Day",
        resources={"preferred_device": "cuda"},
    )
    assert cfg.training.grouping == ["T"] and cfg.augment.grouping == ["T"]
    assert cfg.training.features == ["f"] and cfg.augment.features == ["f"]
    assert cfg.training.timeseries == "Day"
    assert cfg.training.resources.preferred_device == "cuda"
    assert cfg.augment.resources.preferred_device == "cuda"
    cfg.features = ["g"]  # assignment updates the steps too
    assert cfg.training.features == ["g"] and cfg.augment.features == ["g"]
    cfg.training.features.append("h")  # steps never share lists with the workflow
    assert cfg.features == ["g"]


def test_workflow_overrides_bound_fields_of_steps():
    cfg = AEFeatureConfig(
        grouping=["T"], training=AETrainConfig(grouping=["X"], epochs=3)
    )
    assert cfg.training.grouping == ["T"] and cfg.training.epochs == 3


def test_bound_fields_are_not_saved():
    cfg = AEFeatureConfig(grouping=["T"])
    data = cfg.model_dump()
    assert data["grouping"] == ["T"]
    for step in ("training", "run"):
        assert not {"grouping", "features", "resources"} & set(data[step])
    assert "timeseries" not in data["training"]
    assert "model_files" not in data["run"]  # set from the training step's models
    assert "epochs" in data["training"]
    assert AEFeatureConfig.model_validate(data) == cfg


def test_unset_version_is_not_saved():
    data = AEFeatureConfig().model_dump()
    assert "version" not in data and "version" not in data["training"]
    assert "classname" not in data["resources"]  # not a tool config
    assert AEFeatureConfig(version="2.0").model_dump()["version"] == "2.0"


def test_classname_names_the_registered_tool():
    class DemoTool:
        name = "Demo AE Training"
        category = "Analysis"
        config_class = AETrainConfig

    tools.register(DemoTool)
    try:
        expected = f"{DemoTool.__module__}.{DemoTool.__qualname__}"
        assert AETrainConfig().classname == expected
        cfg = AEFeatureConfig()
        assert cfg.training.classname == expected
        assert cfg.classname is None  # no tool registered for the workflow
        data = cfg.model_dump()
        assert data["training"]["classname"] == expected
        assert "classname" in data and data["classname"] is None
        assert AEFeatureConfig.model_validate(data) == cfg
        assert AETrainConfig(classname="my.Tool").classname == "my.Tool"
    finally:
        tools.unregister(DemoTool.name)


def test_workflow_strict():
    assert AETuneConfig().strict is None  # the mode decides: GUI False, batch True
    cfg = AETuneConfig(strict=True)
    assert AETuneConfig.model_validate_json(cfg.model_dump_json()).strict is True
    assert "strict" not in cfg.to_legacy_params()
