# Pair Plot

The `Pair Plot` tool creates a grid of scatter plots, one for each pair of features, colored by the first grouping column. The plots on the diagonal show the distribution of each feature.

**Menu Access:** `Plot` > `Pair Plot`

**Tool panel icon:** ![](/images/analysis/pairplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Pair Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Pair Plot` menu.

3. In the `Configuration: Pair Plot` dialog, select the grouping, the features and the layout:
    - `Grouping`: the category columns. The points are colored by the first one, for example `Treatment`. Further grouping columns are not used.
    - `Grid columns`: the features shown in the columns of the grid.
    - `Same rows as columns`: the rows of the grid show the same features as its columns, which gives a square grid. Uncheck it to choose the row features separately in `Grid rows`, for example to plot a few features against many others. `Grid rows` appears only when `Same rows as columns` is unchecked.
    - `Lower half only`: leaves out the upper half of a square grid. The upper half shows the same plots as the lower half, mirrored. It appears only with `Same rows as columns` checked.
    - `Diagonal`: shows a `Histogram` (the default) or a `KDE` curve of each feature on the diagonal. `Histogram bins` sets the number of bins (default 20). Both apply only to a square grid, with the same features in its rows and columns. Otherwise the grid has no diagonal.
    - `Scatter points`: `Show` all points (the default), or only a random sample. `Samples` sets how many points the sample has (default 20000). The sample is the same every time you run the tool with the same settings, and `Random seed` sets which sample it is. `Samples` and `Random seed` appear only for `sample`. Large tables plot much faster with a sample. The sample applies to the scatter plots. The histograms and KDE curves on the diagonal use all rows.
    - `Legend`: where the legend is shown. Choose `right`, `top`, `bottom` or `left` to place it outside the plots, `inside` to place it inside, or `none` to hide it. `Legend` appears with 1 or more grouping columns. See [Hidden settings](/userguide/dialogs.md#hidden-settings).

    The grid has one plot for each pair of a column feature and a row feature. The dialog warns for more than 50 plots, and shows an error for more than 300.

    ![](/images/analysis/pairplot-config.png)

4. Click `OK`.

5. The plot opens in a new plot window, named after the grouping, for example `Plot: Pair Plot: ['Treatment']`. With a sample, a note below the plots says how many points it shows.

## Example Output

`FAD a1[%]`, `NAD(P)H a2[%]` and `FLIRR`, grouped by `Treatment`, with a sample of 5,000 measurements:
![](/images/analysis/pairplot-results.png)

```{note}
You can zoom into the plot and save it in its plot window. Double-click editing of axes and labels is not available in pair plots. See [The Plot Window](/userguide/plots/plotwindow).
```
