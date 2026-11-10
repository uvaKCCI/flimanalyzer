# Drop Columns

The `Drop Columns` tool removes columns by their names, for example all columns whose names contain `Exc1_`. It also removes a column with an empty header. `Import...` drops the same columns from the files it reads (see [Loading Data](/userguide/data/load.md)), and both use the same settings: a change in one shows in the other.

**Menu Access:** `Data` > `Drop Columns`

1. Select `Data` > `Drop Columns`.

2. In the `Configuration: Drop Columns` dialog, edit the `Drop` table. Each row has:

    - `Text`: the text to look for in the column names.
    - `Match`: `contains` (the default) drops the columns whose names contain the text anywhere; `starts with` and `ends with` drop those whose names start or end with it; `is` drops the column with exactly that name.

    Use `Add Row` and `Remove Rows` to change the list. A column is dropped if it matches any row.

    Below the settings, the dialog shows the columns that would be dropped, for example `Example: drops Exc1_-Ch1-_t1, Exc1_-Ch1-_t2, Exc1_-Ch1-_a1`, followed by how many more columns are dropped.

3. Click `OK`.

The result is `Table: Columns Dropped`, with the same rows as the input.

The default rows drop the columns whose names contain `Exc1_`, `Exc2_` or `Exc3_`: the columns that are not renamed by the default [Rename Columns](/userguide/data/rename.md) replacements.
