# Swarm Plot

The `Swarm Plot` tool creates swarm plots of grouped data.

**Menu Access:** `Plot` > `Swarm Plot`

**Toolbar Icon:** ![](/images/analysis/swarmplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.  
    ```{note}
    A swarm plot draws every data point. For large tables this is slow, and the points crowd together. To plot only a random sample of the points, set `Points` > `Show` to `sample` in the dialog. You can also plot a [summary](/userguide/analysis/summary) of the data instead. This example uses the mean FLIRR of each cell, made with `Summarize` and grouped by `Treatment`, `FOV` and `Cell`:
    ```
    
    ![](/images/analysis/dataframe-summary-grouped.png)

2. Start the Swarm Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Swarm Plot` menu.

3. In the `Configuration: Swarm Plot` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    `Fit axes to the data` is checked by default. The value axes then run from the smallest to the largest value, plus a 5% margin. Uncheck it if the axes should include 0.

    In the example, the mean FLIRR of each cell is plotted, grouped by `Treatment` and `FOV`.

    ![](/images/analysis/swarmplot-config-grouping.png)

4. Click `OK`.

5. Each selected feature is plotted in its own plot window.

```{note}
To change the plot layout, change the order of the grouping columns. See the examples below.
```

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/swarmplot-result1-grouping.png)


**Example Results:** `Grouping` - FOV, Treatment

![](/images/analysis/swarmplot-result2-grouping.png)

```{note}
You can change and save plots as described in the [Plots](/userguide/plots/index) section.
```