# Filtering Data

Data rows can be hidden based on filtering criteria for specific data columns. We distinguish filtering of categorical columns, i.e. columns containing discrete labels, and of columns containing numeric values. 

**Note:** Filtering of data hides the corresponding table rows based on matching filter criteria. The underlying data is not altered and as such filtering events are reversible.

## Filtering categorical columns

Follow these steps to filter rows based on categorical column values:

1. Right click on a categorical column header (indicated by light blue background color).

2. A dialog window opens, displaying the available values found in the particular column. Select the values to be displayed, unselect the values to be hidden in the table.

3. Click `Ok`. The dialog window closes and the table display updates to only show rows with values matching the selected list chosen under step 2.

In the example, the `Ctrl`, `Dox30`, and `Dox60` values are selected for the `Treatment` column. Rows containing `Dox15` or `Dox45` as `Treatment` values are hidden in the table view. The selection of shown and hidden data rows can be updated by right clicking the column header again. 

![](/images/data/category-filter.png)

## Filtering columns with numeric values

Filtering of columns containing numeric values is based on setting min/max value ranges, so called range filters. Rows with column values falling inside the specified range are displayed in the table, values outside that range are hidden from view. A different range can be specified for each column.

Follow these steps to view and modify the filter range for a specific column:

1. Select the `Filter Data` checkbox in the sidebar of the data table window.

2. Click the `Filter Settings...` button.

3. A `Filter Settings` dialog window opens, displaying the currently specified min/max range filters for all columns with numeric values.

4. Update the indvidual range filters as needed. Select the `Use` check box to activate a specific filter. Range filters for which the `Use` checkbox is deselected are ignored.

5. Click `Ok`. The dialog window closes and the table display updates to only show rows with values matching the selected range filters chosen under step 4.

**Note**: The `Use Filters` checkbox in the `Filter Settings` dialog and the `Filter Data` checkbox in the table window allow toggling all selected filters on and off at once. This provides an efficient way to toggle between filtered and original raw data view.

![](/images/data/filter-settings.png)

To adjust a single column range filter, it is more convenient to select the `Filter Data` checkbox in the data table window and then `right click` the header of that column. Adjust the min/max values of the filter as needed and click `Ok`.
