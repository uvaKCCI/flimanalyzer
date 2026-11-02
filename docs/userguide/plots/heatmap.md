# Heatmap

The `Heatmap` tool creates a heatmap of the correlations between the selected features.

**Menu Access:** `Plot` > `Heatmap`

**Toolbar Icon:** ![](/images/analysis/heatmap.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Heatmap tool by clicking on its icon in the tool panel or via the `Plot` > `Heatmap` menu.

3. In the `Configuration: Heatmap` dialog, select the correlation method and the features. In the `Correlation` menu, choose `pearson`, `spearman` or `kendall`, whichever suits your data. The features are the columns with numbers, such as `FAD a1`. Check `Show values` to write each correlation value in its cell of the heatmap. Otherwise the heatmap shows the values only as colors.

    In the example, the amplitudes and lifetimes of FAD and NAD(P)H, and FLIRR, are used, with `pearson` correlation and `Show values` checked. The heatmap uses all rows of the table, without grouping.

    ![](/images/analysis/heatmap-config.png)

4. Click `OK`.

5. The heatmap opens in a plot window, and the correlation values in a new table.

```{note}
The tool also creates a table with the correlation values of the features. See example below.
```

## Example Output

**Example Results:** Heatmap Plot

![](/images/analysis/heatmap-results1.png)


**Example Results:** Automatically Generated Data Table

![](/images/analysis/heatmap-results2.png)

```{note}
You can change and save plots as described in the [Plots](/userguide/plots/index) section.
```
