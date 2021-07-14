# Series Analysis

The `Series Analysis` tool performs an analysis of a data series spread across multiple table columns.  The series analysis is performed across selectable columns for each row.

**Menu Access:** `Analysis` > `Series Analysis`

**Toolbar Icon:** ![](/images/analysis/seriesanalysis.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front. If the series data is spread across multiple rows in a _single__ column, the data can be [pivoted](/userguide/data/pivot/) to arrange associated series data across multiple columns. The table below was created by pivoting the `Treatment` category. Each row represents the data across treatments grouped by `Cell`, `Compartment`, and `FOV`.
 
    ![](/images/analysis/relpivot-result.png)


2. Start the Series Analysis tool by clicking on the icon in the toolbar or via the `Analysis` > `Series Analysis` menu.

3. In the `Configuration: Series Analysis` dialog, select the analysis parameters to calculate and select the data columns to be considered for the series analysis.

    * **Series min:** Calculate minimal value row of selected data feature columns.
    * **Series max:** Calculate maximal value row of selected data feature columns.
    * **Series max-min:** Calculate difference of `Series max` and `Series min`.
    * **Series mean:** Calculate mean value row of selected data feature columns.
    * **Series median:** Calculate median value row of selected data feature columns.
    * **Step delta:** Calculate difference between selected neighboring data feature columns (step-by-step). 
    * **Step delta min:** Calculate minimal value of all delta step values.
    * **Step delta max:** Calculate maximal value of all delta step values.
    * **Merge input:** Copy selected series columns from input table into analysis table.

    ![](/images/analysis/seriesanalysis-config.png)

4. Click `OK`.

5. The calculated data for each series is aggregated in a new table.


## Example Output

**Example Results:** 

![](/images/analysis/seriesanalysis-results.png)