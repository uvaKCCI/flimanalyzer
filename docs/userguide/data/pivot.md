# Pivoting Data

A pivot table summarizes and rearranges data to emphasize specific information. For example, turning the values of one category column into separate columns can show trends across a series of conditions.

**Menu Access:** `Data` > `Pivot`

**Toolbar Icon:** ![](/images/data/pivot.png)

Take the following data table as an example.

![](/images/data/pivot-original.png)

The table has three category columns, `Treatment`, `FOV` (field-of-view), and `Cell`. Multiple measurements were obtained for each cell in each FOV, for a time series of treatment conditions (`ctrl`, `Dox15`, `Dox30`, `Dox45`, `Dox60`).

Say you want to see how `FAD a1[%]` and `NAD(P)H a2[%]` change for each cell over the treatment time series. In the original data, this is hard to see. Pivoting the `Treatment` column and averaging the measurements of each cell in each FOV puts the whole time series of a cell in one row.

1. In the sidebar of the data table, click the `Pivot` button.

2. In the `Pivot data: Groups to pivot` dialog window, select `Treatment`. Leave the other columns unchecked. **Note:** The dialog lists all category columns.

    ![](/images/data/pivot-input.png)

3. Click `OK`.

4. In the `Pivot data: Columns to retain` dialog window, select the numeric columns of interest, for example `FAD a1[%]` and `NAD(P)H a2[%]` for this example.

    ![](/images/data/pivot-columns.png)

5. Click `OK`.

The resulting table looks like the one below. Each row now shows the **mean** values of one cell (one combination of `FOV` and `Cell`). The values of the original `Treatment` column became columns, so each row shows the trend across the treatments for the two selected measurements: `FAD a1[%]` / `ctrl` through `FAD a1[%]` / `Dox60`, and `NAD(P)H a2[%]` / `ctrl` through `NAD(P)H a2[%]` / `Dox60` (the column headers have two lines: the measurement and the treatment). The treatments are in their category order (see [Order Categories](order.md)).

![](/images/data/pivot-result.png)

The `Pivot` tool in the `Data` menu does the same in a single dialog, with the options `Columns to pivot` (for example `Treatment`) and `Features`. [Unpivoting](unpivot.md) turns such columns back into a category column.

The data in this new table can be filtered by category values or by numeric range filters as described in [Filtering Data](filter.md).
