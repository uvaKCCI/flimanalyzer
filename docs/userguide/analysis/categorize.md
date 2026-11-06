# Categorize Data

The `Categorize Data` tool adds a new category column. The value each row gets depends on the range that a feature value falls in, e.g. `low`, `medium` or `high` FLIRR.

**Menu Access:** `Analysis` > `Categorize Data`

**Tool panel icon:** ![](/images/analysis/categorize.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front. The dialog's `Data` choice starts with this table; you can choose another one there (see [Choosing the data](/userguide/dialogs.md#choosing-the-data)).
    ![](/images/data/dataframe.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Categorize Data` menu.

3. In the `Configuration: Categorize Data` dialog, set:
    * `New column`: the name of the new category column (default `New Cat`). If the table already has a column with this name, it is replaced.
    * `Rules`: each rule is one row and sets one value of the new column. Enter the `Value`, the `Feature` it depends on (a numeric column of the table), and the range `Min` < feature value <= `Max`. `Min` must be smaller than `Max`. Use `Add Rule` and `Remove Rules` to add and remove rules. The default rules are `negative` (-100000 to -0.5), `neutral` (-0.5 to 0.5) and `positive` (0.5 to 100000), all on `FLIRR`.

        Rules on the same feature must not overlap; overlapping ranges are an error. Different rules can use different features. If rules on different features match the same row, the first of them sets the row's value.
    * `Default value`: the value for rows that no rule matches (default `unassigned`).
    * `Include the input` (checked by default): keep all columns of the table. If unchecked, the dialog shows `Features`: the result then has only the category columns and the features selected there.

    ![](/images/analysis/categorize-config.png)

    In the example, the column `FLIRR level` gets three values:

    * 0 < FLIRR <= 0.25: `low`
    * 0.25 < FLIRR <= 0.35: `medium`
    * 0.35 < FLIRR <= 1: `high`

    Rows with other FLIRR values get the default value, `unassigned`.

4. Click `OK`.

5. The results are shown in a new table window, `Table: Categorized`. The new category column comes after the other category columns.

## Example Output

![](/images/analysis/categorize-results.png)
