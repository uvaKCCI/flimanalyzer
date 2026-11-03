# Heatmap

The `Heatmap` tool creates a heatmap of the correlations between the selected features. The color scale runs from −1 (negative correlation) through 0 to 1 (positive correlation).

**Menu Access:** `Plot` > `Heatmap`

**Tool panel icon:** ![](/images/analysis/heatmap.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Heatmap tool by clicking on its icon in the tool panel or via the `Plot` > `Heatmap` menu.

3. In the `Configuration: Heatmap` dialog, select the correlation method and the features. In the `Correlation` menu, choose `pearson`, `spearman` or `kendall`, whichever suits your data. The features are the columns with numbers, such as `FAD a1`. Check `Show values` to write each correlation value in its cell of the heatmap. Otherwise the heatmap shows the values only as colors.

    The heatmap always uses all rows of the table. The dialog shows `Grouping`, but the grouping has no effect on the correlations: it only changes the title of the heatmap (`Data grouped by ...` or `Data ungrouped`).

    In the example, the amplitudes and lifetimes of FAD and NAD(P)H, and FLIRR, are used, with `pearson` correlation and `Show values` checked.

    ![](/images/analysis/heatmap-config.png)

4. Click `OK`.

5. The heatmap opens in a plot window, `Plot: Heatmap`, and the correlation values in a table window, `Table: Heatmap Correlation`. The table has a `Feature` column and one column for each feature.

## Example Output

**Example Results:** Heatmap Plot

![](/images/analysis/heatmap-results1.png)


**Example Results:** Correlation Table

![](/images/analysis/heatmap-results2.png)

```{note}
You can zoom into the heatmap and save it in its plot window. Double-click editing of axes and labels is not available in heatmaps. See [The Plot Window](/userguide/plots/plotwindow).
```
