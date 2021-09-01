# Violin Plot

This tool creates violin plots of grouped data.

**Menu Access:** `Analysis` > `Violin Plot`

**Toolbar Icon:** ![](/images/analysis/violinplot.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front.
    ![](/images/data/dataframe.png)

2. Start the Violin Plot tool by clicking on the icon in the toolbar or via the `Analysis` > `Violin Plot` menu.

3. In the `Configuration: Violin Plot` dialog, select the data grouping and data features of interest. Data grouping options are based on the tables category columns,  i.e. `Cell`, `Compartment`, `FOV`, and `Treatment` in this example. Data features correspond to columns with numeric data, `FAD a1`, etc..

    In the example, input data is grouped by `Treatment` and `FOV`.  

    ![](/images/analysis/violinplot-config-grouping.png)

4. Click `OK`.

5. The data for each analysis feature is plotted in its own plot window.

```{note}
The plot layout and grouping of bars can be changed by altering the order of the data grouping elements. See examples below.
```

## Example Output

**Example Results:** `Data Grouping` - Treatment, FOV

![](/images/analysis/violinplot-result1-grouping.png)


**Example Results:** `Data Grouping` - FOV, Treatment

![](/images/analysis/violinplot-result2-grouping.png)

```{note}
Plots can be manipulated and saved as described in the [Plots](/userguide/plots/index) section.