# Relative Change

The `Relative Change` tool divides each feature by its mean (or median) in a reference group, e.g. the control treatment. Plots of the result then show changes relative to the reference.

**Menu Access:** `Analysis` > `Relative Change`

**Tool panel icon:** ![](/images/analysis/relchange.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front. The dialog's `Data` choice starts with this table; you can choose another one there (see [Choosing the data](/userguide/dialogs.md#choosing-the-data)).
    ![](/images/data/dataframe.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Relative Change` menu.

3. In the `Configuration: Relative Change` dialog, set:
    - `Reference statistic`: `mean` (default) or `median` of the reference rows.
    - `Reference column`: the category column that holds the reference value (default `Treatment`).
    - `Reference value`: the value that marks the reference rows, e.g. `ctrl`. The default is `Ctrl`. The value must be one of the values of the reference column; case matters, so `Ctrl` is an error for a table with `ctrl`.

4. Select the grouping and the features. Without grouping, the reference is calculated from all reference rows of the table. If you group by columns other than the reference column, the reference is calculated separately for each of their groups. The reference column itself makes no difference in the grouping.

    In the example, the data is grouped by `Treatment` (the reference column) and `FOV`. For each `FOV` and feature, the tool calculates the mean of the `ctrl` rows and divides the feature's values in that `FOV` by it.

    Other category columns, e.g. `Cell`, don't matter. If a group has no reference rows (here: a `FOV` without `ctrl` rows), its values stay empty, and the log names the groups.

    ![](/images/analysis/relchange-config-grouping.png)

5. Click `OK`.

6. The results are shown in a new table window, `Table: Relative Change`. It has all category columns of the table and the relative values, in columns named `rel <feature>`. The original features are not included.

## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/relchange-result-grouping.png)

To check the result, run [Summarize](/userguide/analysis/summary) on it with the same grouping (`Treatment, FOV`): the mean of each `ctrl` group is 1.
