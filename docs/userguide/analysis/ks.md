# KS - Statistics

The `KS-Stats` tool is a nonparemtric test to check the similarity between the distributions of two samples. In this cases, the two samples of data are based on combinations of one of the following categorical columns: `Cell`, `FOV`, or `Treatment`.

**Menu Access:** `Analysis` > `KS-Statistics`

**Toolbar Icon:** ![](/images/analysis/ks.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front.
    ![](/images/data/exdata_table.png)

2. Start the KS-Stat tool by clicking on the icon in the toolbar or via the `Analysis` > `KS-Stat` menu.

3. In the `Configuration: KS-Statistics` dialog, define the desired categorical column for the `Comparison` parameter and the `alpha` value. `alpha` is the threshold for declaring the two entities dissimilar and will default to 0.05.
    
    ![](/images/analysis/ks-config1.png)

4. Select the data grouping and data features of interest. Data grouping options are based on the tables category columns,  i.e. `Cell`, `Compartment`, `FOV`, and `Treatment` in this example. Data features correspond to columns with numeric data, `FAD a1`, etc..

    In the example, input data is not grouped, and only the FAD a1 data feature is selected. 
    
4. Click `OK`.

5. The analysis results are shown in new data tables, one for each data feature selected. The new tables contain a declaration on if the two compared entities are dissimilar (yes or no), and n-values for each entity being compared, which are just the number of data points of that descriptor. More importantly, the tables displays p-values, statistic value, and critical D values, for each comparison. The p-value comes from the critical D statistic, and the critical D statistic is the max distance between the cumulative distributions of the compared items
## Example Output

**Example Results:** `Comparison` - Treatment and `Data Grouping` - None
![](/images/analysis/ks-results.png)

As shown above, based on the FAD a1 values, all of the treatments are dissimilar from one another. All of the p-values are 0, which is less the the `alpha` value of 0.05.
