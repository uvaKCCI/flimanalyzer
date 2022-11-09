# Scatter Plot

The `Scatter Plot` tool creates scatter plots of grouped data.

**Menu Access:** `Plot` > `Scatter Plot`

**Toolbar Icon:** ![](/images/analysis/scatter.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front.
    ![](/images/data/dataframe.png)

2. Start the Scatter Plot tool by clicking on the icon in the toolbar or via the `Plot` > `Scatter Plot` menu.

3. In the `Configuration: Scatter Plot` dialog, select the data grouping and data features of interest. Data grouping options are based on the tables category columns,  i.e. `Cell`, `Compartment`, `FOV`, and `Treatment` in this example. Data features correspond to columns with numeric data, `FAD a1`, etc..

    In the example, input data is grouped by `Treatment`.  

    ![](/images/analysis/scatter-config1.PNG)

4. Click `OK`.

5. The data for each analysis feature is plotted in its own plot window.

## Example Output

![](/images/analysis/scatter-results.PNG)

```{note}
Plots can be manipulated and saved as described in the [Plots](/userguide/plots/index) section.
```
