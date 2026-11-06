# Filter Tool

The `Filter` tool creates a new table with only the rows you want to keep: rows with selected category values, and rows whose values lie within set ranges.

**Menu Access:** `Data` > `Filter`

**Tool panel icon:** ![](/images/data/filter.png)

The filters of the table window (see [Filtering Data](filter.md)) only hide rows in that window. The `Filter` tool instead creates a new table, `Table: Filtered`, and leaves the original table unchanged. Use it when the filtered rows should be saved, or used as the input of other tools and workflows.

## Filtering the Data

1. Open a data table, then start `Filter` from the menu or the tool panel.

2. Under `Category values to keep`, select a category column in the list on the left. Its values appear on the right, all checked. Uncheck the values whose rows should be dropped. Columns that filter rows are marked with `*`; columns you don't change keep all their rows.

3. Under `Range filters`, check `Use` for the columns to filter and set their limits:
    - `Low` and `High`: rows with a value below `Low` or above `High` are dropped. Rows with a value equal to a limit are kept. Leave a limit empty for no limit on that side.
    - `Drop missing` (checked by default): also drops rows that have no value in the column.

    `Low` can't be larger than `High`; the dialog marks such a row.

    ![](/images/data/filtertool-config.png)

4. Click `OK`. The new table `Table: Filtered` opens in its own window.

A row is kept only if it passes every filter: its category values are among the selected ones, and its values lie within all checked ranges.
