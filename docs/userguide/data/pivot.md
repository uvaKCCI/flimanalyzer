# Pivoting Data

A pivot table summarizes and rearranges data to emphasize specific information. For example, turning the values of one category column into separate columns can show trends across a series of conditions.

**Menu Access:** `Data` > `Pivot`

**Tool panel icon:** ![](/images/data/pivot.png)

Take the following data table as an example.

![](/images/data/pivot-original.png)

The table has three category columns, `Treatment`, `FOV` (field-of-view), and `Cell`. Multiple measurements were obtained for each cell in each FOV, for a time series of treatment conditions (`ctrl`, `Dox15`, `Dox30`, `Dox45`, `Dox60`).

For example, the original data doesn't show clearly how `FAD a1[%]` and `NAD(P)H a2[%]` change for each cell over the treatment time series. Pivoting the `Treatment` column and averaging the measurements of each cell in each FOV puts the whole time series of a cell in one row.

1. In the table window, click `Pivot...`, or select `Data` > `Pivot`. The dialog uses only the rows that the table window shows; rows hidden by filters are left out. From the table window, the dialog opens with that window's table selected.

2. Under `Columns to pivot`, select `Treatment` (the default). The list shows the table's category columns.

3. Under `Features`, select the numeric columns of interest, for example `FAD a1[%]` and `NAD(P)H a2[%]`. By default, all numeric columns are used. Text columns that are not category columns, such as `Source`, are left out of the result.

    Below the settings, the dialog shows the first rows of the result in a small table, and how many rows it has.

4. Click `OK`.

The result opens in a new table window, `Table: Pivoted`. It looks like the one below. Each row now shows the **mean** values of one cell (one combination of `FOV` and `Cell`). The values of the original `Treatment` column became columns, so each row shows the trend across the treatments for the two selected measurements: `FAD a1[%]` / `ctrl` through `FAD a1[%]` / `Dox60`, and `NAD(P)H a2[%]` / `ctrl` through `NAD(P)H a2[%]` / `Dox60` (the column headers have two lines: the measurement and the treatment). The treatments are in their category order (see [Order Category Values](order.md)). A row without a value in a category column (here `Treatment`, `FOV` or `Cell`) is left out of the means; the run summary gives the number of these rows.

![](/images/data/pivot-result.png)

[Unpivoting](unpivot.md) turns such columns back into a category column: `Unpivot...` in the table window, or `Data` > `Unpivot`.

The data in this new table can be filtered by category values or by numeric range filters as described in [Filtering Data](filter.md).
