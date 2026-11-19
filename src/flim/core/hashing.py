"""The algorithms of the content hashes of files, tables and arrays.

The data types call them in their `content_hash` (`flim.core.types.DataType`), which
is how a value is hashed: `DataType.of(value).content_hash(value)`.

A content hash identifies data by what it holds, not by how it is stored in memory
or pickled, so the same data gives the same hash in another session, on another
computer and with another chunking of an image. The run summary lists the hash of
each input (`flim.core.runner`); a later cache can key results by it.

The hash is SHA-256, as the `sha256sum` command gives it for a file:

- a file: its bytes;
- a table (`pandas.DataFrame`): its shape, the names and dtypes of its columns in
  their order, and its rows with their index, as `pandas.util.hash_pandas_object`
  hashes them. That function hashes the values, not a pickle of them; pandas does not
  promise the same hash across its versions, so the run summary records the pandas
  version next to the hash;
- an array (NumPy, Dask, PyTorch): its shape, its dtype and its values in C order.
  A Dask array is read a block of rows at a time, so the hash does not depend on its
  chunks, and the array is never loaded whole.

Prefect's own input hashing (`prefect.utilities.hashing.hash_objects`, MD5 of a JSON
or cloudpickle dump) is not used: pickled bytes change with the Python and library
versions, and a pickled Dask array holds its task graph, not its values.
"""

import hashlib
import json
import os
from typing import Any

# bytes read from a file at a time
BLOCK = 1 << 20
# the bytes of an array hashed at a time (rows of its first axis)
ARRAY_BLOCK = 64 << 20


def file_hash(path: str | os.PathLike) -> str:
    """Return the SHA-256 of a file's bytes, as `sha256sum` gives it.

    Args:
        path: The file.

    Returns:
        The hash, 64 hex digits.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def table_hash(table: Any) -> str:
    """Return the SHA-256 of a table's content.

    Args:
        table: A `pandas.DataFrame`, or a `pandas.Series` (as a table of one column).

    Returns:
        The hash, 64 hex digits.
    """
    import pandas as pd

    kind = b"series\0" if isinstance(table, pd.Series) else b"table\0"
    if isinstance(table, pd.Series):
        table = table.to_frame()
    digest = hashlib.sha256(kind)
    header = {
        "shape": list(table.shape),
        "columns": [[repr(c), str(t)] for c, t in zip(table.columns, table.dtypes)],
        "index": [repr(n) for n in table.index.names],
    }
    digest.update(json.dumps(header).encode())
    rows = pd.util.hash_pandas_object(table, index=True)  # one uint64 per row
    digest.update(rows.to_numpy(dtype="uint64").tobytes())
    return digest.hexdigest()


def array_hash(array: Any) -> str:
    """Return the SHA-256 of an array's content: NumPy, Dask or PyTorch.

    Args:
        array: The array.

    Returns:
        The hash, 64 hex digits.
    """
    import numpy as np

    if type(array).__module__.startswith("torch"):
        array = array.detach().cpu().numpy()
    shape = tuple(int(n) for n in array.shape)
    dtype = np.dtype(array.dtype)
    digest = hashlib.sha256(b"array\0")
    digest.update(json.dumps({"shape": shape, "dtype": dtype.str}).encode())
    if not shape or shape[0] == 0:
        digest.update(np.ascontiguousarray(np.asarray(array)).tobytes())
        return digest.hexdigest()
    row = max(1, dtype.itemsize * int(np.prod(shape[1:], dtype=np.int64)))
    step = max(1, ARRAY_BLOCK // row)
    for start in range(0, shape[0], step):
        # a block of rows in C order: their bytes follow each other as in the whole
        block = np.asarray(array[start : start + step])
        digest.update(np.ascontiguousarray(block).tobytes())
    return digest.hexdigest()
