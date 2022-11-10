# Heatmap

The 'Heatmap` tool creates heatmaps using selected data features.

**Menu Access:** `Plot` > `Heatmap`

**Toolbar Icon:** ![](/images/analysis/heatmap.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front.
    ![](/images/data/dataframe.png)

2. Start the Heatmap tool by clicking on the icon in the toolbar or via the `Analysis` > `Heatmap` menu.

3. In the `Configuration: Heatmap` dialog, select the correlation method and data features of interest. The `Correlation` dropdown menu contains options for the `Pearson`, `Spearman`, and `Kendall` methods. Select the appropriate method for your collected data. Data features correspond to columns with numeric data, `FAD a1`, etc.. The `Overlay Numbers` checkbox also provides the option for the generated heatmap to directly state its correlation value on the plot, as opposed to only showing its color value.

    In the example, input data is ungrouped, which goes for all heatmaps. The `Pearson` correlation method is selected, along with the `Overlay Numbers` option.  

    ![](/images/analysis/heatmap-config.png)

4. Click `OK`.

5. The data for each analysis feature is plotted in its own plot window.

```{note}
A table with the data features and their corresponding correlation value is automatically created. See example below.
```

## Example Output

**Example Results:** Heatmap Plot

![](/images/analysis/heatmap-results1.png)


**Example Results:** Automatically Generated Data Table

![](/images/analysis/heatmap-results2.png)

```{note}
Plots can be manipulated and saved as described in the [Plots](/userguide/plots/index) section.
```
