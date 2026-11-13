# Filtering Data

You can hide data rows based on the values in specific columns. There are two kinds of filters: filters for category columns, which contain labels such as treatment names, and filters for columns with numeric values.

**Note:** Filtering only hides table rows. The data itself is not changed, so you can undo a filter at any time.

## Filtering category columns

Follow these steps to filter rows by the values of a category column:

1. Right-click the header of a category column. Category column headers have a light blue background.

2. A dialog opens with the values found in the column. Check the values to show, and uncheck the values to hide. `Select All` and `Deselect All` check or uncheck all values. The values are listed in their category order (see [Order Category Values](order.md)).

3. Click `OK`. The dialog closes, and the table shows only the rows with the values checked in step 2. If you uncheck values while `Filter Data` is off, the GUI switches `Filter Data` on, because the category filters apply only while it is on.

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

**Note:** The `Filter Data` checkbox in the table window switches all filters of the window on or off at once: the checked range filters and the values hidden in category columns. This is a quick way to switch between the filtered table and the full data. A filter applies only if `Filter Data` is on and the filter itself is on (see [When a filter applies](#when-a-filter-applies)).

**Note:** The filters and `Filter Data` apply only to their table window. A change in one window doesn't change the other windows. A new table window starts with the defaults for new tables (see [Presets](#presets)).

**Note:** Check `Show Dropped` in the `Filter Settings` dialog to see the rows that the range filters hide. When you click `OK`, a new window, `<title> - Discarded`, opens with these rows. Rows hidden only by the values selected in category columns are not in it. In this window, `Filter Data` is off, so that all its rows are shown.

![](/images/data/filter-settings.png)

To change the range filter of a single column, it is quicker to check `Filter Data` in the table window and right-click the header of that column. Change the minimum and maximum of the filter as needed and click `OK`.

## Presets

The buttons of the `Filter Settings` dialog load and save all filters of the table window, as settings of the [Filter tool](filtertool.md): `Filter Data` (the Filter tool's `Use filters`, `enabled` in settings files), the range filters and the values kept in category columns.

* `Load Preset...` shows the filters of the defaults for new tables, of a preset you saved, or of a file (`From file...`). They replace all filters of the window: range filters of other columns are switched off, and other category columns show all their values. A column that the table doesn't have is listed below the filters, and so is the number of filters that a table window doesn't use, for example conditions and groups of the Filter tool. The table window uses the loaded filters when you click `OK`.
    - `From file...` reads a settings file with `Filter` settings, for example one saved with `To file...` or with `Save Settings...` of the `Filter` dialog. It also reads a file of `Save Feature Settings...`: its range filters are switched on, and `Filter Data` is not changed.
* `Save as Preset...` saves the filters of the dialog:
    - `Defaults for new tables`: new table windows start with these range filters, and with `Filter Data` as it is in this window. The values kept in category columns are not part of the defaults. The GUI writes them to the user settings file, so they are used in later sessions too.
    - A preset you saved: replaces it. `New preset...` asks for a name. The presets are in the user settings file. The `Filter` tool's `Load Preset...` offers them too.
    - `To file...`: adds the filters to a settings file as `Filter` settings, as `Save Settings...` of the `Filter` dialog does. The file's other settings are kept. The `Filter` dialog's `Load Settings...` reads it.
* `Remove Presets...` removes presets you saved.

## When a filter applies

A filter applies only if all switches on its way are on: `Filter Data` in the table window, or `Use filters` in the `Filter` tool, then the `enabled` of each group that contains the filter, then the filter's own `Use`. If one of them is off, the filter keeps all rows.

## Filters in settings files and batch mode

The defaults for new tables are the range filters of the [Filter tool](filtertool.md) and the `filters` setting. They are part of the settings: `File` > `Export Settings...` saves them (see [Settings](/userguide/settings)). The filters of a table window are not saved, unless you save them as the defaults, as a preset or to a file. [Batch mode](/userguide/batch) doesn't filter by them: to filter rows there, add a `Filter` step to a workflow file. The filters of a table window apply only to that window, and to the tools started for it: a tool gets only the rows the window shows. To keep a table with only some category values, use the [Filter tool](filtertool.md).
