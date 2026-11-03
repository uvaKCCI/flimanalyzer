# Line Plot

The `Line Plot` tool creates line plots of grouped data. Each point on a line shows the mean of a group. The error bars (or a band, see `Error style`) show a confidence interval (95% by default) or the standard deviation, as set with `Error`.

**Menu Access:** `Plot` > `Line Plot`

**Toolbar Icon:** ![](/images/analysis/lineplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Line Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Line Plot` menu.

3. In the `Configuration: Line Plot` dialog, select the grouping and the features to plot. Data grouping options are based on the tables category columns,  i.e. `Treatment`, `FOV`, and `Cell` in this example. The first column in the grouping list sets the categories along the x axis. Data features correspond to columns with numeric data, `FAD a1`, etc..

    In the example, `FLIRR` is plotted, grouped by `Treatment` and `FOV`.

    ![](/images/analysis/lineplot-config-grouping.png)

4. Click `OK`.

5. Each selected feature is plotted as a separate set of lines in the same plot.

```{note}
To change the plot layout, change the order of the grouping columns. See the examples below.
```

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/lineplot-result1-grouping.png)


In this example, the `Ctrl` values differ from one `FOV` to the next. This makes it hard to compare the trends of the lines. To make this easier, first convert the data with the [Relative Change](/userguide/analysis/relchange/) tool. It turns each value into a fold change relative to the mean or median of a reference group, here `Treatment` > `Ctrl`. Then plot the converted data.   

**Example Results:** `Grouping` - FOV, Treatment, of FLIRR relative to `ctrl` (see [Relative Change](/userguide/analysis/relchange))

![](/images/analysis/lineplot-result2-grouping.png)


```{note}
You can change and save plots as described in the [Plots](/userguide/plots/index) section.
```