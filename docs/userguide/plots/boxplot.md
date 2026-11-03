# Box Plot

The `Box Plot` tool creates box plots of grouped data. Each box shows the median of a group (the line inside the box) and the middle half of its values (the box). The whiskers reach to the smallest and largest values within 1.5 times the box height. Points beyond the whiskers are drawn one by one.

**Menu Access:** `Plot` > `Box Plot`

**Tool panel icon:** ![](/images/analysis/boxplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Box Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Box Plot` menu.

3. In the `Configuration: Box Plot` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    The grouping columns have these roles, in their order in the list:
    - 1st: the boxes along the x axis, one for each value. With only one grouping column, all boxes have the same color.
    - 2nd: the colors of the boxes, shown in the legend.
    - 3rd: a column of plots for each value.
    - 4th: a row of plots for each value.
    - Further grouping columns are not used.

    `Fit axes to the data` is checked by default. The value axes then run from the smallest to the largest value, plus a 5% margin. Uncheck it if the axes should include 0.

    `Single figure` draws the plots of all features as tiles of one figure. `Plots per row` sets how many tiles are in each row (0: about as many rows as columns). Without `Single figure`, each feature gets its own figure. With more than 2 grouping columns, `Single figure` is hidden: each feature then gets its own figure with a grid of plots.

    `Legend` sets where the legend is shown: `right`, `top`, `bottom` or `left` of the plots, `inside` a plot, or `none`. With `Single figure`, the tiles share one legend outside the plots. `Legend` appears only with 2 or more grouping columns. See [Hidden settings](/userguide/dialogs.md#hidden-settings).

    In the example, `FLIRR` is plotted, grouped by `Treatment` and `FOV`.

    ![](/images/analysis/boxplot-config-grouping.png)

4. Click `OK`.

5. Without `Single figure`, each feature is plotted in its own plot window, for example `Plot: Box Plot FLIRR`. With `Single figure`, all features are in one plot window, `Plot: Box Plot`.

```{note}
To change the plot layout, change the order of the grouping columns. See the examples below.
```

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/boxplot-result1-grouping.png)


**Example Results:** `Grouping` - FOV, Treatment

![](/images/analysis/boxplot-result2-grouping.png)

```{note}
You can zoom into the plot, change its axes and labels, and save it in its plot window. See [The Plot Window](/userguide/plots/plotwindow).
```
