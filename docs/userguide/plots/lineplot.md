# Line Plot

The `Line Plot` tool creates line plots based on mean +/- StDev (or S.E.M) of grouped data.

**Menu Access:** `Plot` > `Lineplot`

**Toolbar Icon:** ![](/images/analysis/lineplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. This will bring the selectd table window to the front.
    ![](/images/data/dataframe.png)

2. Start the Line Plot tool by clicking on the icon in the toolbar or via the `Analysis` > `Line Plot` menu.

3. In the `Configuration: Line Plot` dialog, select the data grouping and data features of interest. Data grouping options are based on the tables category columns,  i.e. `Cell`, `Compartment`, `FOV`, and `Treatment` in this example. The first item in the grouping list specifies the categories along the x-axis of the plot. Data features correspond to columns with numeric data, `FAD a1`, etc..

    In the example, input data is grouped by `Treatment` and `FOV`. 

    ![](/images/analysis/lineplot-config-grouping.png)

4. Click `OK`.

5. Each selected data feature is plotted as separate set of lines in the same plot.

```{note}
The plot layout and grouping of bars can be changed by altering the order of the data grouping elements. See examples below.
```

## Example Output

**Example Results:** `Data Grouping` - Treatment, FOV

![](/images/analysis/lineplot-result1-grouping.png)


In this example, the `Ctrl` group values differ for each `FOV`. To facilitate comparison of series trends, the input data may first be converted with the [Relative Change Analysis](/userguide/analysis/relchange/) tool to fold-change values relative to mean/median of reference group, i.e. `Treatment` > `Ctrl`, before plotting.   

**Example Results:** `Data Grouping` - FOV, Treatment after `Relative Change` conversion.

![](/images/analysis/lineplot-result2-grouping.png)


```{note}
Plots can be manipulated and saved as described in the [Plots](/userguide/plots/index) section.
```