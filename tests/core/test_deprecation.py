"""Deprecated names of modules (flim.core.deprecation)."""

import pytest


def test_a_renamed_function_is_found_with_a_warning():
    import flim.core.runner as runner

    with pytest.warns(DeprecationWarning, match="default_max_workers is deprecated and is removed in 0.8.0"):
        old = runner.default_max_workers
    assert old is runner.default_workers


def test_other_missing_names_raise_attribute_error():
    import flim.core.runner as runner

    with pytest.raises(AttributeError, match="no attribute 'gone'"):
        runner.gone
    assert not hasattr(runner, "ToolEntry")
