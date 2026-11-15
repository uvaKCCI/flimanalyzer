"""Helpers: number conversions, combinations of values and clean names."""

import itertools
import math
import re
from collections.abc import Iterable
from operator import itemgetter
from typing import Any


NOISE_UNIT = ["linear", "dB"]


def to_str_sequence(items: Iterable[Any]) -> str:
    """Return the items as text, separated by commas without spaces.

    Args:
        items: The items; each is converted with `str`.

    Returns:
        The text, e.g. `1,a,2.5`; an empty string for no items.
    """
    return ",".join([str(i) for i in items])


def to_db(value: float) -> float:
    """Convert a power ratio to decibels: `10 * log10(value)`.

    Args:
        value: The ratio, greater than 0.

    Returns:
        The ratio in dB.

    Raises:
        ValueError: If `value` is 0 or negative.
    """
    return 10.0 * math.log10(value)


def db_to_linear(db_value: float) -> float:
    """Convert decibels to a power ratio: `10 ** (db_value / 10)`.

    Args:
        db_value: The ratio in dB.

    Returns:
        The ratio.
    """
    return 10.0 ** (db_value / 10.0)


def combine(*args: Any) -> list[tuple]:
    """Return all combinations of the values of the arguments (Cartesian product).

    Args:
        *args: Each a single value or an iterable of values. A value that is not
            iterable counts as one value; a string is iterable and contributes each
            of its characters.

    Returns:
        One tuple per combination, with one value of each argument in argument order;
        the last argument varies fastest. Example: `combine(1, [2, 3])` is
        `[(1, 2), (1, 3)]`.
    """
    largs = [a if isinstance(a, Iterable) else [a] for a in args]
    combos = list(itertools.product(*largs))
    return combos


def permutate(*args: Any) -> list[tuple]:
    """Return the combinations of `combine` as one tuple per argument.

    Args:
        *args: As for `combine`.

    Returns:
        For each argument, its value in every combination, in the order of the
        combinations. Example: `permutate([1, 2], ["a", "b"])` is
        `[(1, 1, 2, 2), ("a", "b", "a", "b")]`.
    """
    combinations = combine(*args)
    splits = []
    for i in range(len(args)):
        splits.append(tuple(map(itemgetter(i), combinations)))
    return splits


def clean(str: str) -> str:
    """Return a text with characters removed or replaced, for tags and folder names.

    Kept are ASCII letters and digits, spaces, line breaks, `.`, `_` and `/`; all
    other characters are removed, including `-`. Then each space and each `/` is
    replaced by `_`.

    Args:
        str: The text.

    Returns:
        The cleaned text, e.g. `a_b_c` for `a b/c` and `ab` for `a#b`.
    """
    rmstr = re.sub(r"[^a-zA-Z0-9 \n._/]", "", str)
    return re.sub("[ /]", "_", rmstr)


def update_left(left: dict, right: dict) -> dict:
    """Return the keys of `left`, with the values of `right` where it has the key.

    Args:
        left: The keys and default values.
        right: The values that replace those of `left`; keys not in `left` are
            ignored.

    Returns:
        A new dict with the keys of `left` in their order.
    """
    return {k: right.get(k) if k in right.keys() else left.get(k) for k in left.keys()}
