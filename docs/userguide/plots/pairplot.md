# Pair Plot

The `Pair Plot` tool creates a grid of scatter plots, one for each pair of features, colored by the first grouping column. The plots on the diagonal show the distribution of each feature.

**Menu Access:** `Plot` > `Pair Plot`

**Toolbar Icon:** ![](/images/analysis/pairplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.

2. Start the Pair Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Pair Plot` menu.

3. In the `Configuration: Pair Plot` dialog, select the grouping, the features and the layout:
    - `Grouping`: the category columns. The points are colored by the first one, for example `Treatment`.
    - `Grid columns`: the features shown in the columns of the grid.
    - `Same rows as columns`: the rows of the grid show the same features as its columns, which gives a square grid. Uncheck it to choose the row features separately in `Grid rows`, for example to plot a few features against many others.
    - `Lower half only`: leaves out the upper half of a square grid. The upper half shows the same plots as the lower half, mirrored.
    - `Diagonal`: shows a `Histogram` or a `KDE` curve of each feature on the diagonal. `Histogram bins` sets the number of bins.
    - `Scatter points`: `Show` all points, or only a random sample. `Samples` sets how many points the sample has. The sample is the same every time you run the tool, and `Random seed` sets which sample it is. Large tables plot much faster with a sample.
    - `Legend`: where the legend is shown. Choose `right`, `top`, `bottom` or `left` to place it outside the plots, `inside` to place it inside, or `none` to hide it.

    ![](/images/analysis/pairplot-config.png)

4. Click `OK`.

5. The plot opens in a new plot window.

## Example Output

`FAD a1[%]`, `NAD(P)H a2[%]` and `FLIRR`, grouped by `Treatment`, with a sample of 5,000 measurements:
![](/images/analysis/pairplot-results.png)
