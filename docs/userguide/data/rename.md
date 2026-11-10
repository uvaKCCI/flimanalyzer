# Rename Columns

The `Rename Columns` tool replaces parts of the column names, for example `Exc1_-Ch1-_` with `trp `, so that `Exc1_-Ch1-_t1` becomes `trp t1`. `Import...` applies the same replacements to the files it reads (see [Loading Data](/userguide/data/load.md)), and both use the same settings: a change in one shows in the other.

**Menu Access:** `Data` > `Rename Columns`

1. Select `Data` > `Rename Columns`.

2. In the `Configuration: Rename Columns` dialog, edit the `Replace` table. Each row has:

    - `Part`: the text to replace. It is replaced wherever it occurs in a column name, not only in whole names.
    - `New text`: its replacement. Empty: the part is removed.

    Use `Add Row` and `Remove Rows` to change the list. The rows apply from top to bottom: each row applies to the names the rows above it produced. A row needs a `Part`.

    Below the settings, the dialog shows an example from the table, for example `Example: Exc1_-Ch1-_t1 → trp t1`, followed by how many more columns are renamed.

3. Click `OK`.

The result is `Table: Renamed`, with the same rows and columns as the input. If two columns would get the same name, the tool doesn't run and names the duplicates.

The default replacements are `Exc1_-Ch1-_` with `trp `, `Exc1_-Ch2-_` with `NAD(P)H ` and `Exc2_-Ch3-_` with `FAD `.
