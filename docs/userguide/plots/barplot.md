# Bar Plot

The `Bar Plot` tool creates bar plots of grouped data. Each bar shows the mean of a group, with the standard deviation or the standard error of the mean (S.E.M.) as error bars.

**Menu Access:** `Plot` > `Bar Plot`

**Toolbar Icon:** ![](/images/analysis/barplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Bar Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Bar Plot` menu.

3. In the `Configuration: Bar Plot` dialog, set up the bars and their error bars.
    - `Orientation`: `vertical` or `horizontal` bars.
    - `Bars`: `single` makes one plot per feature. `stacked` puts all features in one plot, stacked on top of each other. `100% stacked` does the same, with the stacked parts shown as percentages of their sum.
    - `Error bars`: no error bars (`None`), error bars on one side of the bar only (`+`), or on both sides (`+/-`).
    - `Error`: standard deviation (`std`) or standard error of the mean (`s.e.m.`).
    - `Drop missing`: leaves out rows that have no value.
    
    ![](/images/analysis/barplot-config-grouping.png)

4. Select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    In the example, `FLIRR` is plotted, grouped by `Treatment` and `FOV`.

5. Click `OK`.

6. Each selected feature is plotted in its own plot window.

```{note}
To change the plot layout and how the bars are grouped, change the order of the grouping columns. See the examples below.
```

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/barplot-result1-grouping.png)


**Example Results:** `Grouping` - FOV, Treatment

![](/images/analysis/barplot-result2-grouping.png)

```{note}
You can change and save plots as described in the [Plots](/userguide/plots/index) section.
```