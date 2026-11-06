# Line Plot

The `Line Plot` tool creates line plots of grouped data. Each point on a line shows the mean of a group. The error bars (or a band, see `Error style`) show a confidence interval (95% by default) or the standard deviation, as set with `Error`.

**Menu Access:** `Plot` > `Line Plot`

**Tool panel icon:** ![](/images/analysis/lineplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Line Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Line Plot` menu.

3. In the `Configuration: Line Plot` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    The grouping columns have these roles, in their order in the list:
    - 1st: the categories along the x axis.
    - 2nd: the colors of the lines, one line for each value, shown in the legend.
    - 3rd: the line styles (solid, dashed, ...), one for each value.
    - 4th: a column of plots for each value.
    - 5th: a row of plots for each value.

    Without grouping, each feature's values are plotted in the order of the table's rows.

    Set the lines and their error bars:
    - `Error`: a number from 1 to 99 for a confidence interval in percent (default 95), `sd` for the standard deviation, or empty for no error bars.
    - `Error style`: error `bars` at each point, or a `band` around the line.
    - `Markers`: draws a marker at each point of the lines, a different one for each value of the 3rd grouping column. Without a 3rd grouping column, no markers are drawn.

    `Single figure` draws the plots of all features as tiles of one figure. `Plots per row` sets how many tiles are in each row (0: about as many rows as columns). Without `Single figure`, each feature gets its own figure. With more than 3 grouping columns, `Single figure` is hidden: each feature then gets its own figure with a grid of plots.

    `Legend` sets where the legend is shown: `right`, `top`, `bottom` or `left` of the plots, `inside` a plot, or `none`. With `Single figure`, the tiles share one legend outside the plots. `Legend` appears only with 2 or more grouping columns. See [Hidden settings](/userguide/dialogs.md#hidden-settings).

    In the example, `FLIRR` is plotted, grouped by `Treatment` and `FOV`.

    ![](/images/analysis/lineplot-config-grouping.png)

4. Click `OK`.

5. Without `Single figure`, each feature is plotted in its own plot window, for example `Plot: Line Plot: FLIRR`. With `Single figure`, all features are in one plot window, `Plot: Line Plot`.

```{note}
To change the plot layout, change the order of the grouping columns. See the examples below.
```

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/lineplot-result1-grouping.png)


In this example, the `ctrl` values differ from one `FOV` to the next. This makes it hard to compare the trends of the lines. To make this easier, first convert the data with the [Relative Change](/userguide/analysis/relchange) tool. It turns each value into a fold change relative to the mean or median of a reference group, here `Treatment` > `ctrl`. Then plot the converted data.

**Example Results:** `Grouping` - FOV, Treatment, of FLIRR relative to `ctrl` (see [Relative Change](/userguide/analysis/relchange))

![](/images/analysis/lineplot-result2-grouping.png)


```{note}
You can zoom into the plot, change its axes, labels and line colors, and save it in its plot window. See [The Plot Window](/userguide/plots/plotwindow).
```
