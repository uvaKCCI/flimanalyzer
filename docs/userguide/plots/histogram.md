# Frequency Histogram

The `Frequency Histogram` tool creates frequency histograms for grouped data.

**Menu Access:** `Plot` > `Frequency Histogram`

**Toolbar Icon:** ![](/images/analysis/histogram.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front.
    ![](/images/data/dataframe.png)

2. Start the Frequency Histogram tool by clicking on the icon in the toolbar or via the `Plot` > `Frequency Histogram` menu.

3. In the `Configuration: Frequency Histogram` dialog, select the data grouping, data features of interest, and the desired histogram appearance options. Data grouping options are based on the tables category columns,  i.e. `Cell`, `Compartment`, `FOV`, and `Treatment` in this example. Data features correspond to columns with numeric data, `FAD a1`, etc.. The `Type` dropdown menu provides options for four different histogram styles: `bar`, `barstacked`, `step`, and `stepfilled`. The `Stacked` and `Cumulative` checkboxes provide more options on the data viewing. The `Binned Data Table` checkbox generates a separate data table corresponding to the various bins of data from the histogram.

    In the example, input data is grouped by `Treatment` and uses the `bar` histogram style.  

    ![](/images/analysis/histogram-config.png)

4. Click `OK`.

5. The data for each analysis feature is plotted in its own plot window.

## Example Output

Use of the `bar` histogram style:
![](/images/analysis/histogram-results1.png)

Use of the `barstacked` histogram style:
![](/images/analysis/histogram-results2.png)

Use of the `step` histogram style:
![](/images/analysis/histogram-results3.png)

Use of the `stepfilled` histogram style:
![](/images/analysis/histogram-results4.png)

Example of the generated `Binned data table`:
![](/images/analysis/histogram-results1a.png)

```{note}
Plots can be manipulated and saved as described in the [Plots](/userguide/plots/index) section.
```
