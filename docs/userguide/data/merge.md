# Merge Data

The `Merge` tool combines two data tables by matching the values in the category columns they share.

**Menu Access:** `Data` > `Merge`

**Tool panel icon:** ![](/images/data/merge.png)

The `Merge` tool adds the values of one table to the rows of another table that have the same values in the category columns. For example, a row of one table with the `Treatment, FOV, Cell` values `ctrl, a, 1` gets the values of the row with the same `Treatment, FOV, Cell` values in the other table.

To use the `Merge` tool, follow the steps below:

1. Open the two tables to merge. In the example below, the first table is the data with all measurements, the second contains only the FAD a1 mean of each `Treatment, FOV, Cell` group, made with the `Summarize` tool.

    The data:
    ![](/images/data/merge-start.png)

    The mean FAD a1 of each `Treatment, FOV, Cell` group:
    ![](/images/data/merge-summary.png)

2. Start the `Merge` tool from the menu or the tool panel. In the `Configuration: Merge` dialog, select the two tables under `Left` and `Right`, and how they are joined under `Join`:
    - `inner`: only the rows whose category values occur in both tables.
    - `left`: all rows of the left table; values of the right table where they match.
    - `right`: all rows of the right table; values of the left table where they match.
    - `outer`: all rows of both tables.

    `Merge on` sets the category columns whose values have to match. `Automatic` uses all category columns that the two tables share. If the two tables share no category column, the dialog shows an error and the tool doesn't run.

    A row without a value in one of these columns matches no row of the other table. With `left`, `right` or `outer`, the row is kept, without the values of the other table; with `inner`, it is left out. The run summary gives the number of these rows in each table.

    Other columns that both tables have, for example `Source` or a feature in both, are handled by:
    - `Combine identical columns` (checked by default): a column whose values are the same in both tables, in every row where both have a value, becomes one column with its name. Values are compared exactly; with `outer`, `left` or `right`, a row that has a value in only one table takes that value.
    - `Suffix of the first table` and `Suffix of the second table` (default ` (left)` and ` (right)`): the other columns of both tables keep both versions, for example `FLIRR (left)` and `FLIRR (right)`; the run summary lists them. Enter `_x` and `_y` to name them as FLIMAnalyzer 0.6 did.

    ![](/images/data/merge-dialog.png)

3. Click `OK`.

4. A new merged table, `Table: Merged`, is created. In the example, each row of the data has its group's FAD a1 mean in the last column, `FAD a1 mean`:

    ![](/images/data/merge-res1.png) ![](/images/data/merge-res3.png)
