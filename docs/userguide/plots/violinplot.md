# Violin Plot

The `Violin Plot` tool creates violin plots of grouped data. Each violin shows the distribution of a group's values as a smooth outline (a kernel density estimate), mirrored on both sides. The violin is wider where there are more values. Inside each violin, a small box plot shows the median and the middle half of the values.

**Menu Access:** `Plot` > `Violin Plot`

**Tool panel icon:** ![](/images/analysis/violinplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Violin Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Violin Plot` menu.

3. In the `Configuration: Violin Plot` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    The grouping columns have these roles, in their order in the list:
    - 1st: the violins along the x axis, one for each value. With only one grouping column, all violins have the same color.
    - 2nd: the colors of the violins, shown in the legend.
    - 3rd: a column of plots for each value.
    - 4th: a row of plots for each value.
    - Further grouping columns are not used.

    `Fit axes to the data` is checked by default. The value axes then run from the smallest to the largest value, plus a 5% margin. Uncheck it if the axes should include 0.

    `Single figure` draws the plots of all features as tiles of one figure. `Plots per row` sets how many tiles are in each row (0: about as many rows as columns). Without `Single figure`, each feature gets its own figure. With more than 2 grouping columns, `Single figure` is hidden: each feature then gets its own figure with a grid of plots.

    `Legend` sets where the legend is shown: `right`, `top`, `bottom` or `left` of the plots, `inside` a plot, or `none`. With `Single figure`, the tiles share one legend outside the plots. `Legend` appears only with 2 or more grouping columns. See [Hidden settings](/userguide/dialogs.md#hidden-settings).

    In the example, `FLIRR` is plotted, grouped by `Treatment` and `FOV`.

    ![](/images/analysis/violinplot-config-grouping.png)

4. Click `OK`.

5. Without `Single figure`, each feature is plotted in its own plot window, for example `Plot: Violin Plot FLIRR`. With `Single figure`, all features are in one plot window, `Plot: Violin Plot`.

```{note}
To change the plot layout, change the order of the grouping columns. See the examples below.
```

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/violinplot-result1-grouping.png)


**Example Results:** `Grouping` - FOV, Treatment

![](/images/analysis/violinplot-result2-grouping.png)

```{note}
You can zoom into the plot, change its axes and labels, and save it in its plot window. See [The Plot Window](/userguide/plots/plotwindow).
```
