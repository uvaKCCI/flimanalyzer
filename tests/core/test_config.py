from typing import Literal, Optional, Union

import pytest
from pydantic import Field, ValidationError

from flim.core.config import (
    BaseConfig,
    CategoryColumn,
    FeatureColumn,
    Issue,
    Probability,
    Resources,
    TaskConfig,
    column_role,
    fixed_value,
)


class DemoConfig(TaskConfig):
    alpha: Probability = 0.05
    reference: Optional[CategoryColumn] = None
    target: FeatureColumn = "t1"
    mode: Literal["vertical", "horizontal"] = "vertical"
    kind: Literal["only"] = "only"


def test_defaults():
    cfg = TaskConfig()
    assert cfg.grouping == [] and cfg.features == [] and cfg.prefix is None
    assert cfg.resources == Resources()
    assert cfg.resources is not TaskConfig().resources  # not shared between instances


def test_features_all_or_list():
    assert TaskConfig(features="all").features == "all"
    assert TaskConfig(features=["a", "b"]).features == ["a", "b"]
    with pytest.raises(ValidationError):
        TaskConfig(features="some")


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        TaskConfig(groupings=["Treatment"])


def test_assignment_is_validated():
    cfg = DemoConfig()
    with pytest.raises(ValidationError):
        cfg.alpha = 1.5
    with pytest.raises(ValidationError):
        cfg.mode = "diagonal"
    cfg.alpha = 0.01
    assert cfg.alpha == 0.01


def test_resources_defaults_are_fixed():
    with pytest.raises(ValidationError):
        Resources(preferred_device="cuda")
    with pytest.raises(ValidationError):
        Resources(preferred_threads=4)


def test_resources_can_be_widened():
    class WideResources(Resources):
        preferred_threads: int = Field(default=-1, ge=-1)

    class WideConfig(TaskConfig):
        resources: WideResources = Field(default_factory=WideResources)

    assert WideConfig().resources.preferred_threads == -1
    assert (
        WideConfig(resources={"preferred_threads": 4}).resources.preferred_threads == 4
    )


def test_json_round_trip():
    cfg = DemoConfig(grouping=["Treatment"], features="all", alpha=0.1, classname="x.Y")
    assert DemoConfig.model_validate_json(cfg.model_dump_json()) == cfg


def test_column_role():
    fields = DemoConfig.model_fields
    assert column_role(fields["grouping"]) == "category"
    assert column_role(fields["features"]) == "feature"
    assert column_role(fields["reference"]) == "category"
    assert column_role(fields["target"]) == "feature"
    assert column_role(fields["alpha"]) is None
    assert column_role(fields["prefix"]) is None


def test_fixed_value():
    assert fixed_value(DemoConfig, "kind") == (True, "only")
    assert fixed_value(DemoConfig, "mode") == (False, None)
    assert fixed_value(DemoConfig, "alpha") == (False, None)
    assert fixed_value(Resources, "preferred_device") == (True, "cpu")
    assert fixed_value(Resources, "preferred_threads") == (True, 1)


def test_issue():
    issue = Issue("features", "Column 'x' not in the table")
    assert issue.severity == "error"
    assert Issue(None, "Few rows", "warning").severity == "warning"


def test_base_config_metadata_fields():
    cfg = BaseConfig(classname="flim.plugins.Summary", version="1.2")
    assert cfg.classname == "flim.plugins.Summary"
