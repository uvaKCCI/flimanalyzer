# Scatter Plot

The `Scatter Plot` tool creates scatter plots of grouped data.

**Menu Access:** `Plot` > `Scatter Plot`

**Toolbar Icon:** ![](/images/analysis/scatter.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Scatter Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Scatter Plot` menu.

3. In the `Configuration: Scatter Plot` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    `Fit axes to the data` is checked by default. The value axes then run from the smallest to the largest value, plus a 5% margin. Uncheck it if the axes should include 0.

    In the example, `FAD a1[%]` and `NAD(P)H a2[%]` are plotted against each other, grouped by `Treatment`. With exactly two features, `X axis` sets which one is on the x axis. With more features, there is one plot for each pair of features, and the first feature of each pair is on the x axis.

    ![](/images/analysis/scatter-config1.png)

4. Click `OK`.

5. Each pair of features is plotted in its own plot window.

## Example Output

![](/images/analysis/scatter-results.png)

```{note}
You can change and save plots as described in the [Plots](/userguide/plots/index) section.
```
