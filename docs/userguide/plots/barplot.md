# Bar Plot

The `Bar Plot` tool creates bar plots of grouped data. Each bar shows the mean of a group, with the standard deviation or the standard error of the mean (S.E.M.) as error bars.

**Menu Access:** `Plot` > `Bar Plot`

**Tool panel icon:** ![](/images/analysis/barplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Bar Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Bar Plot` menu.

3. In the `Configuration: Bar Plot` dialog, set up the bars and their error bars.
    - `Orientation`: `vertical` or `horizontal` bars.
    - `Bars`: `single` makes one plot per feature. `stacked` puts all features in one plot, stacked on top of each other. `100% stacked` does the same, with the stacked parts shown as percentages of their sum.
    - `Error bars`: no error bars (`None`), error bars on one side of the bar only (`+`), or on both sides (`+/-`).
    - `Error`: standard deviation (`std`) or standard error of the mean (`s.e.m.`).
    - `Drop missing`: leaves out the rows in which a plotted feature has no value before the means are taken. With stacked bars, the means of all features then come from the same rows. Checked by default.
    
    ![](/images/analysis/barplot-config-grouping.png)

4. Select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    With one grouping column, there is one bar for each of its values. With 2 or more grouping columns:
    - the 1st sets the colors of the bars, shown in the legend,
    - the other columns set the bar positions along the axis. Each position is one combination of their values.

    This is the opposite of the box, violin and swarm plots, where the 1st grouping column sets the positions along the x axis. With `stacked` or `100% stacked` bars, all grouping columns set the bar positions, and the colors and the legend show the features.

    `Single figure` draws the plots of all features as tiles of one figure. `Plots per row` sets how many tiles are in each row (0: about as many rows as columns). Without `Single figure`, each feature gets its own figure. With `stacked` or `100% stacked` bars, `Single figure` is hidden: all features are in one plot already.

    `Legend` sets where the legend is shown: `right`, `top`, `bottom` or `left` of the plots, `inside` a plot, or `none`. With `Single figure`, the tiles share one legend outside the plots. `Legend` appears with 2 or more grouping columns, and always with stacked bars. See [Hidden settings](/userguide/dialogs.md#hidden-settings).

    In the example, `FLIRR` is plotted, grouped by `Treatment` and `FOV`.

5. Click `OK`.

6. With `single` bars and without `Single figure`, each feature is plotted in its own plot window, named after the feature, for example `Plot: FLIRR`. With `Single figure`, all features are in one plot window, `Plot: Bar Plot`. Stacked bars of all features are in one plot window, named after the features, for example `Plot: FAD a1[%]|NAD(P)H a2[%]`.

```{note}
To change the plot layout and how the bars are grouped, change the order of the grouping columns. See the examples below.
```

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/barplot-result1-grouping.png)


**Example Results:** `Grouping` - FOV, Treatment

![](/images/analysis/barplot-result2-grouping.png)

```{note}
You can zoom into the plot, change its axes and labels, and save it in its plot window. See [The Plot Window](/userguide/plots/plotwindow).
```
