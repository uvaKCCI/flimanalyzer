# Box Plot

The `Box Plot` tool creates box plots of grouped data. Each box shows the median of a group (the line inside the box) and the middle half of its values (the box). The whiskers reach to the smallest and largest values within 1.5 times the box height. Points beyond the whiskers are drawn one by one.

**Menu Access:** `Plot` > `Box Plot`

**Toolbar Icon:** ![](/images/analysis/boxplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Box Plot tool by clicking on its icon in the tool panel or via the `Plot` > `Box Plot` menu.

3. In the `Configuration: Box Plot` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    `Fit axes to the data` is checked by default. The value axes then run from the smallest to the largest value, plus a 5% margin. Uncheck it if the axes should include 0.

    In the example, `FLIRR` is plotted, grouped by `Treatment` and `FOV`.

    ![](/images/analysis/boxplot-config-grouping.png)

4. Click `OK`.

5. Each selected feature is plotted in its own plot window.

```{note}
To change the plot layout, change the order of the grouping columns. See the examples below.
```

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/boxplot-result1-grouping.png)


**Example Results:** `Grouping` - FOV, Treatment

![](/images/analysis/boxplot-result2-grouping.png)

```{note}
You can change and save plots as described in the [Plots](/userguide/plots/index) section.
```