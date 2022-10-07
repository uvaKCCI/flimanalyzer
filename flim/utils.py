import itertools
import re
from collections.abc import Iterable
from operator import itemgetter


NOISE_UNIT = ["linear", "dB"]


def to_str_sequence(items):
    return ",".join([str(i) for i in items])


def to_db(value):
    return 10.0 * np.log10(value)


def db_to_linear(db_value):
    return 10.0 ** (db_value / 10.0)


def combine(*args):
    largs = [a if isinstance(a, Iterable) else [a] for a in args]
    combos = list(itertools.product(*largs))
    return combos


def permutate(*args):
    combinations = combine(*args)
    splits = []
    for i in range(len(args)):
        splits.append(tuple(map(itemgetter(i), combinations)))
    return splits


def clean(str):
    rmstr = re.sub("[^a-zA-Z0-9 \n\.-_]", "", str)
    return re.sub("[ /]", "_", rmstr)
