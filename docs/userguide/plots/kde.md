# KDE Plot

The `KDE` tool creates kernel density estimate (KDE) plots of grouped data. A KDE plot shows the distribution of a feature as a smooth curve, like a smoothed histogram.

**Menu Access:** `Plot` > `KDE`

**Tool panel icon:** ![](/images/analysis/kde.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the KDE tool by clicking on its icon in the tool panel or via the `Plot` > `KDE` menu.

3. In the `Configuration: KDE` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    Each plot has one curve for each combination of the values of the grouping columns. With 2 grouping columns, the color shows the value of the 1st column and the line style the value of the 2nd (if the 2nd has at most 4 values). Otherwise each curve has its own color. Without grouping, each plot has one curve of all rows. The curves and the x axis cover only the range of the feature's values in the data.

    `Single figure` draws the plots of all features as tiles of one figure. `Plots per row` sets how many tiles are in each row (0: about as many rows as columns). Without `Single figure`, each feature gets its own figure.

    `Legend` sets where the legend is shown: `right`, `top`, `bottom` or `left` of the plots, `inside` a plot, or `none`. With `Single figure`, the tiles share one legend outside the plots. `Legend` appears with 1 or more grouping columns. See [Hidden settings](/userguide/dialogs.md#hidden-settings).

    In the example, `FLIRR` is plotted, grouped by `Treatment` and `FOV`.

    ![](/images/analysis/kde-config.png)

4. Click `OK`.

5. Without `Single figure`, each feature is plotted in its own plot window, for example `Plot: KDE FLIRR`. With `Single figure`, all features are in one plot window, `Plot: KDE`.


## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/kde-results.png)

```{note}
You can zoom into the plot, change its axes, labels and line colors, and save it in its plot window. See [The Plot Window](/userguide/plots/plotwindow).
```
