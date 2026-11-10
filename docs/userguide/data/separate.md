# Separate Categories

The `Separate Categories` tool separates one category column into several, for example `FOV:Cell` back into `FOV` and `Cell`, or a file name such as `Results-ko_01.txt` into `Treatment` `ko` and `Cell` `01`. It has two modes: at delimiters, or by patterns.

**Menu Access:** `Data` > `Separate Categories`

1. Select `Data` > `Separate Categories`.

2. In the `Configuration: Separate Categories` dialog, set:

    - `Column`: the category column to separate.
    - `Separate`: `delimiters` or `patterns` (see below).
    - `Part`: which part of the values to separate: the whole `value`, or, for a path, its `file name`, with or without its extension.
    - `Keep the original column` (checked by default): unchecked, the separated column is removed.

3. Click `OK`.

The result is `Table: Separated`, with the new columns after the separated column.

## At delimiters

The values are separated at any of the `Delimiters` (default `:`, the reverse of `Fuse Categories`).

- `New columns`: the names of the new columns, one per part, in order. An empty name skips that part. If you give no names, they come from the column name separated the same way: `FOV:Cell` gives `FOV` and `Cell`.

A value with more or fewer parts than there are names is not separated: its row gets missing values in the new columns, so that no part ends up in the wrong column. The run summary lists these values.

For example, to separate file names like `Results-ko_01.txt`: `Part` `file name without extension`, `Delimiters` `-` and `_`, and `New columns` empty, `Treatment`, `Cell` (the empty name skips `Results`).

## By patterns

Each pattern makes one new column: its name, and a regular expression whose first group, in parentheses, is the value. These are the same patterns as the filename parser of `Import...` uses (see [Loading Data](/userguide/data/load.md)). For example, the pattern `/data/(.*?)/` takes `ctrl` from `/data/ctrl/FOV1/cell3.txt`. Backslashes in Windows paths are matched as `/`.

A group that matches nothing gives `?`. A value that the pattern doesn't match gets a missing value. The run summary reports a pattern that matched no value at all.
