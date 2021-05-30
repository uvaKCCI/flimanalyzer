# Box Plot

The `Box Plot` tool creates box plots based on mean +/- StDev (or S.E.M) of grouped data.

**Menu Access:** `Analysis` > `Boxplot`

**Toolbar Icon:** ![](/images/analysis/boxplot.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This will bring the selectd table window to the front.
    ![](/images/data/dataframe.png)

2. Start the Bar Plot tool by clicking on the icon in the toolbar or via the `Analysis` > `Box Plot` menu.

3. In the `Configuration: Box Plot` dialog, select the data grouping and data features of interest. Data grouping options are based on the tables category columns,  i.e. `Cell`, `Compartment`, `FOV`, and `Treatment` in this example. Data features correspond to columns with numeric data, `FAD a1`, etc..

    In the example, input data is grouped by `Treatment` and `FOV`.  

    ![](/images/analysis/boxplot-config-grouping.png)

4. Click `OK`.

5. The data for each analysis feature is plotted in its own plot window.

```{note}
The plot layout and grouping of bars can be changed by altering the order of the data grouping elements. See examples below.
```

## Example Output

**Example Results:** `Data Grouping` - Treatment, FOV

![](/images/analysis/boxplot-result1-grouping.png)


**Example Results:** `Data Grouping` - FOV, Treatment

![](/images/analysis/boxplot-result2-grouping.png)

```{note}
Plots can be manipulated and saved as described in the [Plots](/userguide/plots/index) section.
```