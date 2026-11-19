# Fuse Categories

The `Fuse Categories` tool joins two or more category columns into one, for example `FOV` and `Cell` into `FOV:Cell`. A row with `FOV` `1` and `Cell` `2` gets the value `1:2`. This gives each cell an identifier that is unique across fields of view, for tools that group by a single column. `Separate Categories` reverses it (see [Separate Categories](/userguide/data/separate.md)).

**Menu Access:** `Data` > `Fuse Categories`

**Tool panel icon:** ![](/images/data/fuse.png)

1. Select `Data` > `Fuse Categories`.

2. In the `Configuration: Fuse Categories` dialog, set:

    - `Columns to fuse`: the category columns (at least two), in the order their values are joined. Use `Up` and `Down` to change the order.
    - `Delimiter` (default `:`): joins the column names and the values. Spaces count, for example ` - ` gives `1 - 2`; a tab is typed `\t`.
    - `New column`: the new column's name. Empty: the column names joined by the delimiter, for example `FOV:Cell`.
    - `Keep the original columns` (checked by default): unchecked, the fused columns are removed.

    Below the settings, the dialog shows an example in a small table: a few rows with different values, the columns to fuse, and the new column, marked `→`. For example, `FOV` `1` and `Cell` `2` next to `→ FOV:Cell` `1:2`. If the table already has a column with a new column's name, the new column gets a number, for example `FOV_1`, so that no column is replaced; the dialog warns about it, and so does the run summary. A fused column that is removed (`Keep the original columns` unchecked) does not count: the new column can have its name, for example `FOV` for `FOV` and `Cell` fused.

3. Click `OK`.

The result is `Table: Fused`, with the new column after the last fused column, or in its place if the fused columns are removed. Its categories are the combinations that occur in the table, in the order of the fused columns' categories. A row with a missing value in one of the columns gets a missing value.

If the delimiter occurs in a column name or in a value (for example the time point `0:30` with the delimiter `:`), separating the column back would be ambiguous. The dialog warns about this at `Delimiter` before you run the tool; the tool still runs and reports the warning in the run summary. Choose another delimiter if you want to separate the column again.
