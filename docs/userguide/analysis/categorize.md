# Categorize Data

The `Categorize Data` tool adds a new category column. The value each row gets depends on the range that a feature value falls in, e.g. `low`, `medium` or `high` FLIRR.

**Menu Access:** `Analysis` > `Categorize Data`

**Toolbar Icon:** ![](/images/analysis/categorize.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front.
    ![](/images/data/dataframe.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Categorize Data` menu.

3. In the `Configuration: Categorize Data` dialog, set:
    * `New column`: the name of the new category column.
    * `Rules`: each rule is one row and sets one value of the new column. Enter the `Value`, the `Feature` it depends on (one of the table's columns), and the range `Min` < feature value <= `Max`. Use `Add Rule` and `Remove Rules` to add and remove rules. Different rules can use different features. If more than one rule matches a row, the first of them sets the row's value.
    * `Default value`: the value for rows that no rule matches.
    * `Include the input`: keep all columns of the table. If unchecked, the dialog shows `Features`: the result then has only the category columns and the features selected there.

    ![](/images/analysis/categorize-config.png)

    In the example, the column `FLIRR level` gets three values:

    * 0 < FLIRR <= 0.25: `low`
    * 0.25 < FLIRR <= 0.35: `medium`
    * 0.35 < FLIRR <= 1: `high`

    Rows with other FLIRR values get the default value, `unassigned`.

4. Click `OK`.

5. The results are shown in a new data table. The new category column comes after the other category columns.

## Example Output

![](/images/analysis/categorize-results.png)
