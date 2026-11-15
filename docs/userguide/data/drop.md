# Drop Columns

The `Drop Columns` tool removes columns by their names, for example all columns whose names contain `Exc1_`. It also removes a column with an empty header. The built-in `Import` workflow drops the same columns with a Drop Columns step of its own (see [Import Tables](/userguide/data/load.md#import-tables)); changing this tool's settings doesn't change it.

**Menu Access:** `Data` > `Drop Columns`

**Tool panel icon:** ![](/images/data/dropcolumns.png)

1. Select `Data` > `Drop Columns`.

2. In the `Configuration: Drop Columns` dialog, edit the `Drop` table. Each row has:

    - `Text`: the text to look for in the column names.
    - `Match`: `contains` (the default) drops the columns whose names contain the text anywhere; `starts with` and `ends with` drop those whose names start or end with it; `is` drops the column with exactly that name.

    Use `Add Row` and `Remove Rows` to change the list. A column is dropped if it matches any row.

    Below the settings, the dialog shows the columns that would be dropped in a small table, for example `Exc1_-Ch1-_t1`. Above the table, it says how many more columns are dropped.

3. Click `OK`.

The result is `Table: Columns Dropped`, with the same rows as the input.

The default rows drop the columns whose names contain `Exc1_`, `Exc2_` or `Exc3_`: the columns that are not renamed by the default [Rename Columns](/userguide/data/rename.md) replacements.
