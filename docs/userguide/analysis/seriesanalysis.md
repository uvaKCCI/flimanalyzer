# Series Analysis

The `Series Analysis` tool performs an analysis of a data series spread across multiple table columns.  The series analysis is performed across selectable columns for each row.

**Menu Access:** `Analysis` > `Series Analysis`

**Toolbar Icon:** ![](/images/analysis/seriesanalysis.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front. If the series data is spread across multiple rows in a _single__ column, the data can be [pivoted](/userguide/data/pivot/) to arrange associated series data across multiple columns. The table below was created by pivoting the `Treatment` category. Each row represents the data across treatments grouped by `Cell`, `Compartment`, and `FOV`.
 
    ![](/images/analysis/relpivot-result.png)


2. Start the Series Analysis tool by clicking on the icon in the toolbar or via the `Analysis` > `Series Analysis` menu.

3. In the `Configuration: Series Analysis` dialog, select the analysis parameters to calculate and select the data columns to be considered for the series analysis.

    * **Series min:** calculate minimal value row of selected data feature columns.
    * **Series max:** calculate maximal value row of selected data feature columns.
    * **Series max-min:** calculate difference of `Series max` and `Series min`.
    * **Series mean:** calculate mean value row of selected data feature columns.
    * **Series median:** calculate median value row of selected data feature columns.
    * **Step delta:** calculate difference between selected neighboring data feature columns (step-by-step). 
    * **Step delta min:** calculate minimal value of all delta step values.
    * **Step delta max:** calculate maximal value of all delta step values.
    * **Merge input:** copy selected series columns from input table into analysis table.


    In the example, we select all treatments for the `rel FAD a[%]` data.  

    ![](/images/analysis/seriesanalysis-config.png)

4. Click `OK`.

5. The calculated data for each series is aggregated in a new table.


## Example Output

**Example Results:** 

![](/images/analysis/seriesanalysis-results.png)