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


def get_version():
    """The FLIMAnalyzer version: of the installed package, else of the source
    checkout; "unknown" if neither can be determined."""
    try:
        from flim._version import version  # written by setuptools_scm on install

        return version
    except ImportError:
        pass
    try:
        import pkg_resources

        return pkg_resources.get_distribution("flimanalyzer").version
    except Exception:
        pass
    try:
        from setuptools_scm import get_version as scm_version

        return scm_version(root="..", relative_to=__file__)
    except Exception:
        return "unknown"
