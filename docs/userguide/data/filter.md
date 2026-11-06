# Filtering Data

You can hide data rows based on the values in specific columns. There are two kinds of filters: filters for category columns, which contain labels such as treatment names, and filters for columns with numeric values.

**Note:** Filtering only hides table rows. The data itself is not changed, so you can undo a filter at any time.

## Filtering category columns

Follow these steps to filter rows by the values of a category column:

1. Right-click the header of a category column. Category column headers have a light blue background.

2. A dialog opens with the values found in the column. Check the values to show, and uncheck the values to hide. `Select All` and `Deselect All` check or uncheck all values. The values are listed in their category order (see [Order Categories](order.md)).

3. Click `OK`. The dialog closes, and the table shows only the rows with the values checked in step 2.

In the example, the `ctrl`, `Dox30`, and `Dox60` values are selected for the `Treatment` column. Rows with `Dox15` or `Dox45` as `Treatment` are hidden in the table. To change which rows are shown, right-click the column header again.

![](/images/data/category-filter.png)

## Filtering columns with numeric values

Columns with numeric values are filtered by a range: a minimum and a maximum value. These filters are called range filters. The table shows the rows whose values are inside the range, and hides the rows whose values are outside it. Each column can have its own range.

Follow these steps to view and change the range filters:

1. Select the `Filter Data` checkbox in the table window.

2. Click the `Filter Settings...` button.

3. The `Filter Settings` dialog opens. It shows the current minimum and maximum of the range filter for each column with numeric values.

4. Change the range filters as needed. Check `Use` to switch a filter on. Filters whose `Use` box is unchecked are ignored.

5. Click `OK`. The dialog closes, and the table shows only the rows whose values are inside the ranges of the filters switched on in step 4. While the dialog is open, it shows how many rows these filters hide (`Dropped from view`) and how many remain.

**Note:** The `Use Filters` checkbox in the `Filter Settings` dialog and the `Filter Data` checkbox in the table window switch all the checked filters on or off at once. This is a quick way to switch between the filtered table and the full data.

![](/images/data/filter-settings.png)

To change the range filter of a single column, it is quicker to check `Filter Data` in the table window and right-click the header of that column. Change the minimum and maximum of the filter as needed and click `OK`.

## Filters in settings files and batch mode

The range filters are the same in all table windows. They are part of the settings: `File` > `Export Settings...` saves them, and [batch mode](/userguide/batch) uses them when they are switched on (see [Settings](/userguide/settings)). The values selected in category columns are not saved in settings files and are not used in batch mode. To keep a table with only some category values, use the [Filter tool](filtertool.md).
