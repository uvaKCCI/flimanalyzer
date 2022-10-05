# Swarm Plot

This tool creates swarm plots of grouped data.

**Menu Access:** `Plot` > `Swarm Plot`

**Toolbar Icon:** ![](/images/analysis/swarmplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front.  
    ```{note}
    The plotting function is limited to 1000 datapoints so for large datasets with more than 1000 rows it may be advised to create a [Summary Table](/userguide/analysis/summary) first.
    ```
    
    ![](/images/analysis/dataframe-summary-grouped.png)

2. Start the Swarm Plot tool by clicking on the icon in the toolbar or via the `Analysis` > `Swarm Plot` menu.

3. In the `Configuration: Swarm Plot` dialog, select the data grouping and data features of interest. Data grouping options are based on the tables category columns,  i.e. `Cell`, `Compartment`, `FOV`, and `Treatment` in this example. Data features correspond to columns with numeric data, `FAD a1`, etc..

    In the example, input data is grouped by `Treatment` and `FOV`.  

    ![](/images/analysis/swarmplot-config-grouping.png)

4. Click `OK`.

5. The data for each analysis feature is plotted in its own plot window.

```{note}
The plot layout and grouping of bars can be changed by altering the order of the data grouping elements. See examples below.
```

## Example Output

**Example Results:** `Data Grouping` - Treatment, FOV

![](/images/analysis/swarmplot-result1-grouping.png)


**Example Results:** `Data Grouping` - FOV, Treatment

![](/images/analysis/swarmplot-result2-grouping.png)

```{note}
Plots can be manipulated and saved as described in the [Plots](/userguide/plots/index) section.
```