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

    Below the settings, the dialog shows an example from the first row, for example `Example: FOV 1, Cell 2 → FOV:Cell 1:2`.

3. Click `OK`.

The result is `Table: Fused`, with the new column after the last fused column. Its categories are the combinations that occur in the table, in the order of the fused columns' categories. A row with a missing value in one of the columns gets a missing value.

If the delimiter occurs in a column name or in a value (for example the time point `0:30` with the delimiter `:`), separating the column back would be ambiguous. The dialog warns about this at `Delimiter` before you run the tool; the tool still runs and reports the warning in the run summary. Choose another delimiter if you want to separate the column again.
