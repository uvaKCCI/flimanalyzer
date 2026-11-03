# Order Categories

The `Order Categories` tool sets the order of the values of category columns, for example the treatments of a time series, and sorts the rows by them.

**Menu Access:** `Data` > `Order Categories`

**Tool panel icon:** ![](/images/data/order.png)

The other tools use this order: for the groups in summaries, for the bars, boxes and lines along the axes of plots, and for the entries in legends. By default, the values are sorted as text when the data are loaded: capital letters before lowercase letters, and `10` before `2`. For example, `Dox15` comes before `ctrl`.

## Example

In the following example, the values of `Treatment` are put in the order of the time series: `ctrl`, `Dox15`, `Dox30`, `Dox45`, `Dox60`.

1. Start the tool from the menu or the tool panel.

2. Under `Value order`, the list on the left shows the category columns of the table. Select a column to see its values on the right, in their current order. Check the column to apply the order shown. Changing the order of a column's values checks it.

3. Change the order of the values:
    - `Up` and `Down` move the selected value.
    - `Sort` sorts the values alphabetically, as text (so `10` comes before `2`).
    - `Data Order` restores the current order of the values in the table.

4. Click `OK`. A new table, `Table: Reordered`, is created with the new order. Its rows are sorted by the checked columns.

![](/images/data/order-config.png)
