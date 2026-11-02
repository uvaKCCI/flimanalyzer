# Relative Change

The `Relative Change` tool divides each feature by its mean (or median) in a reference group, e.g. the control treatment. Plots of the result then show changes relative to the reference.

**Menu Access:** `Analysis` > `Relative Change`

**Toolbar Icon:** ![](/images/analysis/relchange.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front.
    ![](/images/data/dataframe.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Relative Change` menu.

3. In the `Configuration: Relative Change` dialog, set:
    - `Reference column`: the category column that holds the reference value.
    - `Reference value`: the value that marks the reference rows, e.g. `ctrl`.
    - `Reference statistic`: `mean` or `median` of the reference rows.

4. Select the grouping and the features. If you also group by other columns, the reference is calculated separately for each of their groups.

    In the example, the data is grouped by `Treatment` (the reference column) and `FOV`. For each `FOV` and feature, the tool calculates the mean of the `ctrl` rows and divides the feature's values in that `FOV` by it.

    ![](/images/analysis/relchange-config-grouping.png)

5. Click `OK`.

6. The results are shown in a new data table. The relative values are in columns named `rel <feature>`.

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/relchange-result-grouping.png)

To check the result, run [Summarize](/userguide/analysis/summary) on it with the same grouping (`Treatment, FOV`): the mean of each `ctrl` group is 1.
