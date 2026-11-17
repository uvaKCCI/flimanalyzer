# Filtering Data

You can hide data rows based on the values in specific columns. There are two kinds of filters in a table window: filters for category columns, which contain labels such as treatment names, and filters for columns with numeric values (features). Each kind has its own switch in the side bar of the table window: `Filter Categories` and `Filter Features`.

**Note:** Filtering only hides table rows. The data itself is not changed, so you can undo a filter at any time.

## Filtering category columns

Follow these steps to filter rows by the values of a category column:

1. Right-click the header of a category column. Category column headers have a light blue background.

2. A dialog opens with the values found in the column. Check the values to show, and uncheck the values to hide. `Select All` and `Deselect All` check or uncheck all values. The values are listed in their category order (see [Order Category Values](order.md)).

3. Click `OK`. The dialog closes, and the table shows only the rows with the values checked in step 2. If you uncheck values while `Filter Categories` is off, the GUI switches `Filter Categories` on. `Filter Features` does not change.

In the example, the `ctrl`, `Dox30`, and `Dox60` values are selected for the `Treatment` column. Rows with `Dox15` or `Dox45` as `Treatment` are hidden in the table. To change which rows are shown, right-click the column header again.

![](/images/data/category-filter.png)

The `Filter Categories` checkbox switches the hidden category values on or off. When it is off, the table shows the rows of all values, and the window keeps the values you unchecked. When you check it again, the same values are hidden again.

## Filtering columns with numeric values

Columns with numeric values are filtered by a range: a minimum and a maximum value. These filters are called range filters. The table shows the rows whose values are inside the range, and hides the rows whose values are outside it. Each column can have its own range.

Follow these steps to view and change the range filters:

1. Click the `Filter Features...` button in the table window.

2. The `Filter Features` dialog opens. It shows the current minimum and maximum of the range filter for each column with numeric values. A column without a range filter has no limits (`-inf` and `inf`) until you set them. The `Dropped view` column shows how many of the window's rows each filter hides; it shows `---` for a filter that is switched off.

3. Change the range filters as needed. Check `Use` to switch a filter on. Filters whose `Use` box is unchecked are ignored. `Select All` and `Deselect All` check or uncheck `Use` for all filters.

4. The `Filter Features` checkbox at the top of the dialog switches all range filters on or off. While it is off, the list of filters is greyed out. When you check the `Use` box of a filter, or click `Select All`, the GUI switches `Filter Features` on.

5. Click `OK`. The dialog closes, and the table shows only the rows whose values are inside the ranges of the filters switched on in step 3. The `Filter Features` checkbox of the table window shows the value of the dialog. While the dialog is open, it shows how many rows these filters hide (`Dropped from view`) and how many remain.

**Note:** The `Filter Features` checkbox in the table window switches all range filters on or off at once. This is a quick way to switch between the filtered table and the full data. A range filter applies only if `Filter Features` is on and the filter itself is on (see [When a filter applies](#when-a-filter-applies)).

**Note:** The filters and their switches apply only to their table window. A change in one window doesn't change the other windows. A new table window starts with the defaults for new tables (see [Presets](#presets)).

**Note:** Check `Show Dropped` in the `Filter Features` dialog to see the rows that the range filters hide. When you click `OK`, a new window, `<title> - Discarded`, opens with these rows. Rows hidden by the values selected in category columns (with `Filter Categories` on) are not in it. In this window, `Filter Features` and `Filter Categories` are off, so that all its rows are shown.

![](/images/data/filter-settings.png)

To change the range filter of a single column, it is quicker to check `Filter Features` in the table window and right-click the header of that column. Change the minimum and maximum of the filter as needed and click `OK`.

## Presets

The buttons of the `Filter Features` dialog load and save the range filters of the table window and the `Filter Features` switch, as a part of the settings of the [Filter tool](filtertool.md): its range filters (`features` in settings files). The values hidden in category columns are not part of them.

* `Load Preset...` shows the range filters of the defaults for new tables, of a preset you saved, or of a file (`From file...`). They replace the range filters of the window: range filters of other columns are switched off. A column that the table doesn't have is listed below the filters, and so is the number of category and other filters of the Filter tool that the dialog doesn't use. `Filter Features` is set as in the preset or file: it is on only if `Use range filters` and `Use filters` of the Filter tool are both on. The table window uses the loaded filters when you click `OK`.
    - `From file...` reads a settings file with `Filter` settings, for example one saved with `To file...` or with `Save Settings...` of the `Filter` dialog. It also reads a file of `Save Feature Settings...`: its range filters are switched on, and `Filter Features` is not changed.
* `Save as Preset...` saves the range filters and `Filter Features` of the dialog:
    - `Defaults for new tables`: new table windows start with these range filters, and with `Filter Features` as it is in this window. The values hidden in category columns are not part of the defaults, and new table windows start with `Filter Categories` as before. The GUI writes the defaults to the user settings file, so they are used in later sessions too.
    - A preset you saved: replaces it. `New preset...` asks for a name. The presets are in the user settings file. The `Filter` tool's `Load Preset...` offers them too.
    - `To file...`: writes the range filters and `Filter Features` to a settings file as the range filters of the `Filter` settings (`features`). In an existing file, only the range filters are replaced: the category filters, the other filters, `Use filters` and the file's other settings are kept. The `Filter` dialog's `Load Settings...` reads it.
* `Remove Presets...` removes presets you saved.

## When a filter applies

A filter applies only if all switches on its way are on:

* In a table window: `Filter Features` for the range filters, `Filter Categories` for the hidden category values, then the filter's own `Use`.
* In the `Filter` tool: `Use filters`, then the switch of the part that contains the filter (`Use range filters`, `Use category filters` or `Use other filters`), then the switch of each group that contains the filter, then the filter's own `Use`.

If one of them is off, the filter keeps all rows. A switch can only switch filters off: a filter that is on in a part that is off keeps all rows.

## Filters in settings files and batch mode

The defaults for new tables are the range filters of the [Filter tool](filtertool.md) and the `filters` setting. They are part of the settings: `File` > `Export Settings...` saves them (see [Settings](/userguide/settings)). The filters of a table window are not saved, unless you save them as the defaults, as a preset or to a file. [Batch mode](/userguide/batch) doesn't filter by them: to filter rows there, add a `Filter` step to a workflow file. The filters of a table window apply only to that window, and to the tools started for it: a tool gets only the rows the window shows. To keep a table with only some category values, use the [Filter tool](filtertool.md).
