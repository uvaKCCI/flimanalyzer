# Series Analysis

The `Series Analysis` tool analyzes a series of values that is spread across several columns of a table, e.g. the values of a time series after the table has been pivoted. It calculates statistics of the series in each row.

**Menu Access:** `Analysis` > `Series Analysis`

**Toolbar Icon:** ![](/images/analysis/seriesanalysis.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front.

    If the series is spread across the rows of a single column, first [pivot](/userguide/data/pivot) the table, so that each value of the series has its own column. The table below was created by pivoting the `Treatment` column. Each row holds the mean `FAD a1[%]` and `NAD(P)H a2[%]` of one cell for each treatment.

    ![](/images/analysis/relpivot-result.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Series Analysis` menu.

3. In the `Configuration: Series Analysis` dialog, select the `Statistics` to calculate. Under `Features`, select the columns of the series, in their order (e.g. `FAD a1[%]` of `ctrl` through `Dox60`):
    * `series_min`, `series_max`, `series_mean`, `series_median`: the minimum, maximum, mean and median of the series.
    * `series_range`: the maximum minus the minimum.
    * `delta`: the difference between each column and the column before it.
    * `delta_min`, `delta_max`, `delta_sum`: the smallest difference, the largest difference, and the sum of all differences.
    * `delta_cum`: the running total of the differences, starting from the first column.
    * `delta_norm`: each difference divided by the total change from the first to the last column.

    `Include the input` also copies the series' columns into the result.

    ![](/images/analysis/seriesanalysis-config.png)

4. Click `OK`.

5. The results are shown in a new data table, with one row for each row of the input.

## Example Output

![](/images/analysis/seriesanalysis-results.png)
