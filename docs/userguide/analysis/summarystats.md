# Summary Table

The `Summary Table` tool calculates counts, min, max, mean, median (50th percentile), 25th percentile, and 75th percentile, StDev, S.E.M,  of grouped data.

**Menu Access:** `Analysis` > `Summary Table`

**Toolbar Icon:** ![](/images/analysis/summary.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This will bring the selectd table window to the front.
    ![](/images/data/dataframe.png)

2. Start the Summary Table tool by clicking on the icon in the toolbar or via the `Analysis` > `Summary Table` menu.

3. In the `Configuration: Summary Table` dialog, select the analysis features, data grouping and data features of interest. Data grouping options are based on the tables category columns,  i.e. `Cell`, `Compartment`, `FOV`, and `Treatment` in this example. Data features correspond to columns with numeric data, `FAD a1`, etc..

    ![](/images/analysis/summary-config-nogrouping.png)

4. Click `OK`.

5. The analysis results are shown in new data table, with each row representing one particular data group and aggregated numbers shown in individual columns.

    **Example Results:** `Data Grouping` - None
    ![](/images/analysis/summary-result1-nogrouping.png)

    **Example Results:** `Data Grouping` - Treatment, FOV
    ![](/images/analysis/summary-result1-grouping.png)
