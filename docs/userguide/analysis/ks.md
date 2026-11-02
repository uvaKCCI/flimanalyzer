# KS-Statistics

The `KS-Statistics` tool tests whether two samples come from the same distribution. It uses the two-sample Kolmogorov-Smirnov test, which makes no assumption about the shape of the distributions (it is nonparametric). The samples are the values of a feature for two values of a category column, e.g. for `ctrl` and `Dox15` in `Treatment`. All pairs of values are compared.

**Menu Access:** `Analysis` > `KS-Statistics`

**Toolbar Icon:** ![](/images/analysis/ks.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front.
    ![](/images/data/exdata_table.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `KS-Statistics` menu.

3. In the `Configuration: KS-Statistics` dialog, select under `Compare` the category column whose values you want to compare. Then set the `Significance level` (alpha, default 0.05). The p-value is the probability of seeing a difference this large if both samples came from the same distribution. Two samples are marked dissimilar when the p-value is below the significance level and the KS statistic is above its critical value (both are shown in the results).

4. Select the grouping and the features. If you group by columns other than the compared one, the values are compared separately within each group, e.g. within each `FOV`.

    In the example, the data is not grouped, and only `FAD a1` is selected.

    ![](/images/analysis/ks-config1.png)

5. Click `OK`.

6. The results are shown in one new data table per feature. For each pair of compared values, the table shows whether they are dissimilar, the number of data points in each (n), the p-value, the KS statistic (a measure of how different the two samples are) and its critical value.

## Example Output

**Example Results:** `Compare` - Treatment, `Grouping` - none

![](/images/analysis/ks-results.png)
