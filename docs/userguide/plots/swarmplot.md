# Swarm Plot

The `Swarm Plot` tool creates swarm plots of grouped data. Each point is one value, that is one row of the table. The points of a group are placed side by side so that they do not overlap. The swarm then shows how many values a group has and how they are spread.

**Menu Access:** `Plot` > `Swarm Plot`

**Tool panel icon:** ![](/images/analysis/swarmplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ```{note}
    A swarm plot draws every data point. For large tables this is slow, and the points crowd together. To plot only a random sample of the points, set `Points` > `Show` to `sample` in the dialog (see step 3). You can also plot a [summary](/userguide/analysis/summary) of the data instead. This example uses the mean FLIRR of each cell, made with `Summarize` and grouped by `Treatment`, `FOV` and `Cell`:
    ```

    ![](/images/analysis/dataframe-summary-grouped.png)

2. Start the Swarm Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Swarm Plot` menu.

3. In the `Configuration: Swarm Plot` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    The grouping columns have these roles, in their order in the list:
    - 1st: the swarms along the x axis, one for each value. With only one grouping column, all points have the same color.
    - 2nd: the colors of the points, shown in the legend.
    - 3rd: a column of plots for each value.
    - 4th: a row of plots for each value.
    - Further grouping columns are not used.

    `Fit axes to the data` is checked by default. The value axes then run from the smallest to the largest value, plus a 5% margin. Uncheck it if the axes should include 0.

    `Single figure` draws the plots of all features as tiles of one figure. `Plots per row` sets how many tiles are in each row (0: about as many rows as columns). Without `Single figure`, each feature gets its own figure. With more than 2 grouping columns, `Single figure` is hidden: each feature then gets its own figure with a grid of plots.

    `Legend` sets where the legend is shown: `right`, `top`, `bottom` or `left` of the plots, `inside` a plot, or `none`. With `Single figure`, the tiles share one legend outside the plots. `Legend` appears only with 2 or more grouping columns. See [Hidden settings](/userguide/dialogs.md#hidden-settings).

    `Points` sets which points are drawn. `Show`: `all` points (the default), or a random `sample`. `Samples` sets how many points the sample has (default 2000), and `Random seed` which sample it is. The sample is the same every time you run the tool with the same settings. It is taken from all rows of the table, before they are grouped. `Samples` and `Random seed` appear only for `sample`.

    In the example, the mean FLIRR of each cell is plotted, grouped by `Treatment` and `FOV`.

    ![](/images/analysis/swarmplot-config-grouping.png)

4. Click `OK`.

5. Without `Single figure`, each feature is plotted in its own plot window, for example `Plot: Swarm Plot FLIRR`. With `Single figure`, all features are in one plot window, `Plot: Swarm Plot`.

With a sample, a note below the plot says how many points it shows, for example `2,000 samples of 25,000 measurements shown`. If some points do not fit in their swarm, they are drawn at its edges, and a note below the plot says so. Then plot fewer points, for example a smaller sample.

```{note}
To change the plot layout, change the order of the grouping columns. See the examples below.
```

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/swarmplot-result1-grouping.png)


**Example Results:** `Grouping` - FOV, Treatment

![](/images/analysis/swarmplot-result2-grouping.png)

```{note}
You can zoom into the plot, change its axes and labels, and save it in its plot window. See [The Plot Window](/userguide/plots/plotwindow).
```
