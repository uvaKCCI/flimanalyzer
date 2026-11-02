# Merge Data

The `Merge` tool combines two data tables by matching the values in the category columns they share.

**Menu Access:** `Data` > `Merge`

**Toolbar Icon:** ![](/images/data/merge.png)

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

    `Merge on` sets the category columns whose values have to match. `Automatic` uses all category columns that the two tables share.

    ![](/images/data/merge-dialog.png)

3. Click `OK`.

4. A new merged table is created. In the example, each row of the data has its group's FAD a1 mean in the last column, `FAD a1 mean`:

    ![](/images/data/merge-res1.png) ![](/images/data/merge-res3.png)
