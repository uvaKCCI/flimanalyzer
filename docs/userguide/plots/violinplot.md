# Violin Plot

The `Violin Plot` tool creates violin plots of grouped data.

**Menu Access:** `Plot` > `Violin Plot`

**Toolbar Icon:** ![](/images/analysis/violinplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Violin Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Violin Plot` menu.

3. In the `Configuration: Violin Plot` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    `Fit axes to the data` is checked by default. The value axes then run from the smallest to the largest value, plus a 5% margin. Uncheck it if the axes should include 0.

    In the example, `FLIRR` is plotted, grouped by `Treatment` and `FOV`.

    ![](/images/analysis/violinplot-config-grouping.png)

4. Click `OK`.

5. Each selected feature is plotted in its own plot window.

```{note}
To change the plot layout, change the order of the grouping columns. See the examples below.
```

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/violinplot-result1-grouping.png)


**Example Results:** `Grouping` - FOV, Treatment

![](/images/analysis/violinplot-result2-grouping.png)

```{note}
You can change and save plots as described in the [Plots](/userguide/plots/index) section.