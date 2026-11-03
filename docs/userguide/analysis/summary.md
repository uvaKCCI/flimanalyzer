# Summarize

The `Summarize` tool calculates the count, minimum, maximum, mean, median (50th percentile), 25th and 75th percentiles, standard deviation, standard error of the mean and sum for each group of the data.

**Menu Access:** `Analysis` > `Summarize`

**Toolbar Icon:** ![](/images/analysis/summary.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front.
    ![](/images/data/dataframe.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Summarize` menu.

3. In the `Configuration: Summarize` dialog, select the `Statistics` to calculate, the `Grouping` and the `Features`. You can group by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numeric data, such as `FAD a1`.

    `Single table` puts all features into one table. Uncheck it to get one table per feature.

    In the example, `count`, `mean`, `std` (standard deviation), `sem` (standard error of the mean) and `median` are calculated for `FAD a1[%]` and `FLIRR`.

    ![](/images/analysis/summary-config-nogrouping.png)

4. Click `OK`.

5. The results are shown in a new data table, with a row for each group and a column for each feature and statistic. The column headers have two lines: the feature and the statistic.

## Example Output

**Example Results:** `Grouping` - none

![](/images/analysis/summary-result1-nogrouping.png)

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/summary-result1-grouping.png)
