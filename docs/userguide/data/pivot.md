# Pivoting Data

A pivot table summarizes and rearranges data to emphasize specific information. For example, transposing specific row values observed in a single column into separate adjacent columns can be useful to display summary trends across multiple dataseries.

**Menu Access:** `Data` > `Pivot`

Let's take the following data table.

![](/images/data/pivot-original.png)

The table has four categorical columns, `Cell`, `Compartment`, `FOV` (field-of-view), and `Treatment`. Multiple measurements were obtained for each Cell, Compartment, FOV for a defined timeseries of Treatment conditions (t0=Ctrl, t1=Dox15, t2=Dox30, t3=Dox45, t4=Dox60). Each data row contains a label indicating the association of the row's values with a specific Cell, Compartment, FOV, at a given Treatment timepoint.

Let's say we're interested in the trend of `FAD a1[%]` and `NAD(P)H a2[%]` for each cell. Looking at the original data, it is hard to see the trend for select measurements in each cell across the treatment time axis. Pivoting the treatment column and summarizing the measurements (mean aggregates) for each cell in each FOV and compartment can help with the exploration of trends over the treatment time series.

1. In the sidebar of the data table, click the `Pivot` button.

2. In the `Pivot Data` dialog window, select the `Treatment` option. Leave the other options deselected. **Note:** The window will show all categorical column headers as selectable options.

    ![](/images/data/pivot-input.png)

3. Click `Ok`.

4. In the next dialog window, select the numeric columns of interest, e.g. `FAD a1[%]` and `NAD(P)H a2[%]` for this example.

    ![](/images/data/pivot-columns.png)

5. Click `Ok`.

The resulting table looks like the one below. Note how each row now shows the **summarized (mean) value** for a given `Cell`, `Compartment`, `FOV`. The values of the original `Treatment` column were rearranged (pivoted) into separate columns such that each row now shows the trend across `Treatment` groups for the two selected measurements, e.g. `FAD a1[%] Ctrl` through `FAD a1[%] Dox60` and `NAD(P)H a2[%] Ctrl` through `NAD(P)H a2[%] Dox60`.

![](/images/data/pivot-result.png)

Data in this newly generated table can be filtered by categorical values or numeric range filters as described [above](#filtering-data).
