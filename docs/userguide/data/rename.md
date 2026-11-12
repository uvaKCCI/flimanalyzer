# Rename Columns

The `Rename Columns` tool replaces parts of the column names, for example `Exc1_-Ch1-_` with `trp `, so that `Exc1_-Ch1-_t1` becomes `trp t1`. The built-in `Import` workflow applies the same replacements with a Rename Columns step of its own (see [Import Tables](/userguide/data/load.md#import-tables)); changing this tool's settings doesn't change it.

**Menu Access:** `Data` > `Rename Columns`

**Tool panel icon:** ![](/images/data/renamecolumns.png)

1. Select `Data` > `Rename Columns`.

2. In the `Configuration: Rename Columns` dialog, edit the `Replace` table. Each row has:

    - `Part`: the text to replace. It is replaced wherever it occurs in a column name, not only in whole names.
    - `New text`: its replacement. Empty: the part is removed.

    Spaces count in both, also at the start and end: `trp ` (with a space) turns `Exc1_-Ch1-_t1` into `trp t1`, while `trp` would give `trpt1`. A tab is typed `\t`.

    Use `Add Row` and `Remove Rows` to change the list. The rows apply from top to bottom: each row applies to the names the rows above it produced. A row needs a `Part`.

    Below the settings, the dialog shows an example from the table, for example `Example: Exc1_-Ch1-_t1 → trp t1`, followed by how many more columns are renamed.

3. Click `OK`.

The result is `Table: Renamed`, with the same rows and columns as the input. If two columns would get the same name, the tool doesn't run and names the duplicates.

The default replacements are `Exc1_-Ch1-_` with `trp `, `Exc1_-Ch2-_` with `NAD(P)H ` and `Exc2_-Ch3-_` with `FAD `.
