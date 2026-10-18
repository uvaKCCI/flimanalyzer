import flim._version as v


def test_version_module_is_generated():
    assert isinstance(v.__version__, str) and v.__version__
    assert isinstance(v.__dirty__, bool)
