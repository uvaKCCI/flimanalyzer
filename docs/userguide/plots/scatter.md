# Scatter Plot

The `Scatter Plot` tool creates scatter plots of grouped data, one for each pair of the selected features.

**Menu Access:** `Plot` > `Scatter Plot`

**Tool panel icon:** ![](/images/analysis/scatter.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Scatter Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Scatter Plot` menu.

3. In the `Configuration: Scatter Plot` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`. Each combination of the values of the grouping columns gets its own color, shown in the legend.

    With exactly two features, `X axis` sets which one is on the x axis. With more features, there is one plot for each pair of features, and the first feature of each pair is on the x axis. Many features make many pairs: the dialog warns for more than 50 plots, and shows an error for more than 300.

    `Fit axes to the data` is checked by default. The value axes then run from the smallest to the largest value, plus a 5% margin. Uncheck it if the axes should include 0.

    `Points` sets which points are drawn. `Show`: `all` points (the default), or a random `sample`. `Samples` sets how many points the sample has (default 20000), and `Random seed` which sample it is. The sample is the same every time you run the tool with the same settings, and all plots show the same rows. `Samples` and `Random seed` appear only for `sample`. Large tables plot much faster with a sample.

    `Single figure` draws all plots as tiles of one figure. `Plots per row` sets how many tiles are in each row (0: about as many rows as columns). Without `Single figure`, each pair of features gets its own figure.

    `Legend` sets where the legend is shown: `right`, `top`, `bottom` or `left` of the plots, `inside` a plot, or `none`. With `Single figure`, the tiles share one legend outside the plots. `Legend` appears with 1 or more grouping columns. See [Hidden settings](/userguide/dialogs.md#hidden-settings).

    In the example, `FAD a1[%]` and `NAD(P)H a2[%]` are plotted against each other, grouped by `Treatment`.

    ![](/images/analysis/scatter-config1.png)

4. Click `OK`.

5. Without `Single figure`, each pair of features is plotted in its own plot window, for example `Plot: Scatter Plot: ('FAD a1[%]', 'NAD(P)H a2[%]')`. With `Single figure`, all pairs are in one plot window, `Plot: Scatter Plot`. With a sample, a note below the plots says how many points it shows.

## Example Output

![](/images/analysis/scatter-results.png)

```{note}
You can zoom into the plot, change its axes and labels, and save it in its plot window. See [The Plot Window](/userguide/plots/plotwindow).
```
