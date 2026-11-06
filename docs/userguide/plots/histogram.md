# Frequency Histogram

The `Frequency Histogram` tool creates frequency histograms for grouped data. By default, the y axis shows the percentage of the measurements in each bin: of each group's measurements, or with `Stacked`, of all measurements.

**Menu Access:** `Plot` > `Frequency Histogram`

**Tool panel icon:** ![](/images/analysis/histogram.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Frequency Histogram tool by clicking on its icon in the tool panel or via the `Plot` > `Frequency Histogram` menu.

3. In the `Configuration: Frequency Histogram` dialog, select the grouping, the features to plot and how the histogram looks. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. Each plot has one histogram for each combination of the values of the grouping columns.

    The features are listed in a table, with a row for each column with numbers, such as `FAD a1`. Check `Use` to plot a feature, and set its `Min`, `Max` and `Bins` in the same row. If you leave `Min` or `Max` empty, the smallest or largest value in the data is used. `Bins` is 30 by default.
    - `Auto min/max range` uses each feature's smallest and largest value in the data. The `Min` and `Max` in the table are greyed out and not used, but kept.
    - `Same bins for all` gives all features the same number of bins. When you check it, all rows get the `Bins` of the row you changed last (or of the first checked row). Changing `Bins` in one row then changes it in all rows.
    - `Load Feature Settings...` and `Save Feature Settings...` load and save the ranges and bins (see [Settings](/userguide/settings)).

    How the histogram looks:
    - `Style`: `bar`, `barstacked`, `step` (the default) or `stepfilled`.
    - `Stacked`: stacks the histograms of the groups on top of each other. The percentages are then of all measurements, so that the stack shows the whole data. Without it, each group's percentages are of the group's own measurements.
    - `Cumulative`: each bin shows its own value plus the values of all bins before it.
    - `Density`: scales each histogram so that its area is 1 (with `Stacked`: the area of the whole stack), instead of showing percentages. The y axis is then labelled `density`.
    - `Binned data table`: also creates a table of the values of each bin, for each feature.

    `Single figure` draws the plots of all features as tiles of one figure. `Plots per row` sets how many tiles are in each row (0: about as many rows as columns). Without `Single figure`, each feature gets its own figure.

    `Legend` sets where the legend is shown: `right`, `top`, `bottom` or `left` of the plots, `inside` a plot, or `none`. With `Single figure`, the tiles share one legend outside the plots. `Legend` appears with 1 or more grouping columns. See [Hidden settings](/userguide/dialogs.md#hidden-settings).

    In the example, `FAD a1[%]` is plotted from 50 to 90 with 40 bins, grouped by `Treatment`, in the `bar` style, with `Binned data table` checked.

    ![](/images/analysis/histogram-config.png)

4. Click `OK`.

5. Without `Single figure`, each feature is plotted in its own plot window, for example `Plot: Frequency Histo Plot: FAD a1[%]`. With `Single figure`, all features are in one plot window, `Plot: Frequency Histogram`.

    With `Binned data table`, each feature also gets a table window, for example `Table: Frequency Histo Table: FAD a1[%]`. Its columns are `bin edge low` and `bin edge high`, and one column for each group with the percentages in its bins, for example `ctrl [rel %]`. With `Density`, the group columns hold the densities instead, for example `ctrl [density]`. Without grouping, there is one column of all rows, `all [rel %]`.

## Example Output

**Example Results:** Use of the `bar` histogram style:

![](/images/analysis/histogram-results1.png)

**Example Results:** Use of the `barstacked` histogram style:

![](/images/analysis/histogram-results2.png)

**Example Results:** Use of the `step` histogram style:

![](/images/analysis/histogram-results3.png)

**Example Results:** Use of the `stepfilled` histogram style:

![](/images/analysis/histogram-results4.png)

**Example Results:** Generated `Binned data table`:

![](/images/analysis/histogram-results1a.png)

```{note}
You can zoom into the plot, change its axes and labels, and save it in its plot window. See [The Plot Window](/userguide/plots/plotwindow).
```
