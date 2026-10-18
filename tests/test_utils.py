import pytest

from flim import utils


def test_to_str_sequence():
    assert utils.to_str_sequence([1, "a", 2.5]) == "1,a,2.5"


def test_combine_scalars_and_iterables():
    assert utils.combine(1, [2, 3]) == [(1, 2), (1, 3)]


def test_permutate_splits_combinations_per_argument():
    assert utils.permutate([1, 2], ["a", "b"]) == [(1, 1, 2, 2), ("a", "b", "a", "b")]


def test_db_to_linear():
    assert utils.db_to_linear(10.0) == pytest.approx(10.0)
    assert utils.db_to_linear(0.0) == pytest.approx(1.0)


@pytest.mark.xfail(raises=NameError, strict=True, reason="flim/utils.py does not import numpy")
def test_to_db():
    assert utils.to_db(10.0) == pytest.approx(10.0)


def test_clean_replaces_spaces_and_slashes():
    assert utils.clean("a b/c") == "a_b_c"
    assert utils.clean("a#b") == "ab"
