# KS-Statistics

The `KS-Statistics` tool tests whether two samples come from the same distribution. It uses the two-sample Kolmogorov–Smirnov test, which makes no assumption about the shape of the distributions (it is nonparametric). The samples are the values of a feature for two values of a category column, e.g. for `ctrl` and `Dox15` in `Treatment`. All pairs of values are compared.

**Menu Access:** `Analysis` > `KS-Statistics`

**Tool panel icon:** ![](/images/analysis/ks.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front. The dialog's `Data` choice starts with this table; you can choose another one there (see [Choosing the data](/userguide/dialogs.md#choosing-the-data)).
    ![](/images/data/exdata_table.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `KS-Statistics` menu.

3. In the `Configuration: KS-Statistics` dialog, set:
    - `Compare`: the category column whose values you want to compare (default `Treatment`). It must have at least 2 values.
    - `Significance level`: alpha, one of 0.1, 0.05 (default), 0.025, 0.01, 0.005 and 0.001.

    The p-value is the probability of seeing a difference this large if both samples came from the same distribution. The critical value of the KS statistic is D = c × √((n1 + n2) / (n1 × n2)), where n1 and n2 are the numbers of data points in the two samples, and c depends on the significance level: 1.22 (0.1), 1.36 (0.05), 1.48 (0.025), 1.63 (0.01), 1.73 (0.005), 1.95 (0.001). Two samples are marked dissimilar when the p-value is below the significance level and the KS statistic is above its critical value.

4. Select the grouping and the features. If you group by columns other than the compared one, the values are compared separately within each group, e.g. within each `FOV`.

    In the example, the data is not grouped, and only `FAD a1` is selected.

    ![](/images/analysis/ks-config1.png)

5. Click `OK`.

6. The results are shown in one new table window per feature, `Table: KS-stats: <feature>`. Each row is one pair of compared values, e.g. for `Compare` set to `Treatment`:
    - The grouping columns other than the compared one. Without them, a column `Grouping` with the value `none`.
    - `Treatment 1`, `Treatment 2` and `Treatment 1 & 2`: the two compared values, and both together, e.g. `ctrl-Dox15`.
    - `dissimilar (<0.05)`: `Yes` or `No`.
    - `n (Treatment 1)`, `n (Treatment 2)`: the number of data points in each sample.
    - `p-values`, `statistic` (the KS statistic, a measure of how different the two samples are) and `critical D (0.05)` (its critical value).

## Example Output

**Example Results:** `Compare` - Treatment, `Grouping` - none

![](/images/analysis/ks-results.png)
