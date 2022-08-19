import itertools
from collections.abc import Iterable 
from operator import itemgetter


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
