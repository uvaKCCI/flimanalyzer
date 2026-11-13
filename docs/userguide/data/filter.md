# Filtering Data

You can hide data rows based on the values in specific columns. There are two kinds of filters: filters for category columns, which contain labels such as treatment names, and filters for columns with numeric values.

**Note:** Filtering only hides table rows. The data itself is not changed, so you can undo a filter at any time.

## Filtering category columns

Follow these steps to filter rows by the values of a category column:

1. Right-click the header of a category column. Category column headers have a light blue background.

2. A dialog opens with the values found in the column. Check the values to show, and uncheck the values to hide. `Select All` and `Deselect All` check or uncheck all values. The values are listed in their category order (see [Order Category Values](order.md)).

3. Click `OK`. The dialog closes, and the table shows only the rows with the values checked in step 2.

In the example, the `ctrl`, `Dox30`, and `Dox60` values are selected for the `Treatment` column. Rows with `Dox15` or `Dox45` as `Treatment` are hidden in the table. To change which rows are shown, right-click the column header again.

![](/images/data/category-filter.png)

## Filtering columns with numeric values

Columns with numeric values are filtered by a range: a minimum and a maximum value. These filters are called range filters. The table shows the rows whose values are inside the range, and hides the rows whose values are outside it. Each column can have its own range.

Follow these steps to view and change the range filters:

1. Select the `Filter Data` checkbox in the table window.

2. Click the `Filter Settings...` button.

3. The `Filter Settings` dialog opens. It shows the current minimum and maximum of the range filter for each column with numeric values. A column without a range filter has no limits (`-inf` and `inf`) until you set them. The `Dropped view` column shows how many of the window's rows each filter hides; it shows `---` for a filter that is switched off.

4. Change the range filters as needed. Check `Use` to switch a filter on. Filters whose `Use` box is unchecked are ignored.

5. Click `OK`. The dialog closes, and the table shows only the rows whose values are inside the ranges of the filters switched on in step 4. While the dialog is open, it shows how many rows these filters hide (`Dropped from view`) and how many remain.

**Note:** The `Use Filters` checkbox in the `Filter Settings` dialog and the `Filter Data` checkbox in the table window switch all the checked filters on or off at once. This is a quick way to switch between the filtered table and the full data. A table window that opens while `Filter Data` is on shows only the rows inside the ranges too.

**Note:** Check `Show Dropped` in the `Filter Settings` dialog to see the rows that the range filters hide. When you click `OK`, a new window, `<title> - Discarded`, opens with these rows. Rows hidden only by the values selected in category columns are not in it. In this window, `Filter Data` is off, so that all its rows are shown.

![](/images/data/filter-settings.png)

To change the range filter of a single column, it is quicker to check `Filter Data` in the table window and right-click the header of that column. Change the minimum and maximum of the filter as needed and click `OK`.

## Filters in settings files and batch mode

The range filters are the same in all table windows, and they are the range filters of the [Filter tool](filtertool.md). They are part of the settings: `File` > `Export Settings...` saves them, and [batch mode](/userguide/batch) uses the Filter tool's filters when `Filter Data` is switched on (see [Settings](/userguide/settings)). The values selected in category columns in a table window are not saved in settings files and are not used in batch mode. They apply only to that window, and to the tools started for it: a tool gets only the rows the window shows. To keep a table with only some category values, use the [Filter tool](filtertool.md).
