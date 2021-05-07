# Working with Data Tables

After [opening](/userguide/files.html#open-data-file) or [importing](/userguide/files.html#import-data-files) files, the data are displayed in a spreadsheet window (table).

Columns containing text or information parsed from filenames during import are specified as categorical data columns. They have limited, and usually fixed, number of discrete possible values. Headers of categorical columns have a light blue background; all other column headers are displayed with a gray background.

![](/images/data/dataframe.png)

## Adjusting Precision

The `Precision` control field in each data table window sets the number of decimal places displayed for non-integer numbers.  For example, a precision value of `3` means that non-integer numbers are displayed with three decimal places.

**Note:** Changing of the `Precision` value changes the displayed number but the underlying raw data number remains unchanged. 

![](/images/data/precision.png)

---

## Filtering Data

Data rows can be hidden based on filtering criteria for specific data columns. We distinguish filtering of categorical columns, i.e. columns containing discrete labels, and of columns containing numeric values. 

**Note:** Filtering of data hides the corresponding table rows based on matching filter criteria. The underlying data is not altered and as such filtering events are reversible.

### Filtering categorical columns

Follow these steps to filter rows based on categorical column values:

1. Right click on a categorical column header (indicated by light blue background color).

2. A dialog window opens, displaying the available values found in the particular column. Select the values to be displayed, unselect the values to be hidden in the table.

3. Click `Ok`. The dialog window closes and the table display updates to only show rows with values matching the selected list chosen under step 2.

In the example, the `Ctrl`, `Dox30`, and `Dox60` values are selected for the `Treatnent` column. Rows containing `Dox15` or `Dox45` as `Treatment` values are hidden in the table view. The selection of shown and hidden data rows can be updated by right clicking the column header again. 

![](/images/data/category-filter.png)

### Filtering columns with numeric values

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

---

## Pivoting Data

A pivot table summarizes and rearranges data to emphasize specific information. For example, transposing specific row values observed in a single column into separate adjacent columns can be useful to display summary trends across multiple dataseries.

Let's take the following data table.

![](/images/data/pivot-original.png)

The table has four categorical columns, `Cell`, `Compartment`, `FOV` (field-of-view), and `Treatment`. Multiple measurements were obtained for each Cell, Compartment, FOV for a defined timeseries of Treatment conditions (t0=Ctrl, t1=Dox15, t2=Dox30, t3=Dox45, t4=Dox60). Each data row contains a label indicating the association of the row's values with a specific Cell, Compartment, FOV, at a given Treatment timepoint.

Let's say we're interested in the trend of `FAD a1[%]` and `NAD(P)H a2[%]` for each cell. Looking at the original data, it is hard to comprehend the trend for select measurements in each cell across the treatment time axis. Pivoting the treatment column and summarizing the measurements (mean aggregates) for each cell in each FOV and compartment can help with the exploration of trends over the treatment time series.

1. In the sidebar of the data table, click the `Pivot` button.

2. In the `Pivot Data` dialog window, select the `Treatment` option. Leave the other options deselected. **Note:** The window will show all categorical column headers as selectable options.

    ![](/images/data/pivot-input.png)

3. Click `Ok`.

4. In the next dialog window, select the numeric columns of interest, e.g. `FAD a1[%]` and `NAD(P)H a2[%]` for this example.

    ![](/images/data/pivot-columns.png)

5. Click `Ok`.

The resulting table looks like the one below. Note how each row now shows the **summarized (mean) value** for a given `Cell`, `Compartment`, `FOV`. The values of the original `Treatment` column were rearranged (pivoted) into separate columns such that each row now shows the trend across `Treatemnt` groups for the two selected measurements, e.g. `FAD a1[%] Ctrl` through `FAD a1[%] Dox60` and `NAD(P)H a2[%] Ctrl` through `NAD(P)H a2[%] Dox60`.

![](/images/data/pivot-result.png)

Data in this newly generated table can be filtered by categorical values or numeric range filters as described [above](#filtering-data).

---

## Splitting Data

In some cases it may be desirable to split datasets into non-overlapping subsets based on categorical groups. The table has four categorical columns, `Cell`, `Compartment`, `FOV` (field-of-view), and `Treatment`. 

Follow these steps to split this table into a set of tables where each resulting table contains the data corresponding to a specific `FOV`.

1. Click the `Split` button in the data table's sidebar.

2. In the next `Split Data` dialog window, select the `FOV` option. Leave the other options unselected.

    ![](/images/data/split-input.png)

3. Click `Ok`.

The `FOV` column in the original table contained five distinct values: `a`, `b`, `c`, `d`, and `e`. The split operation creates five new tables, one for each of the `FOV` labels.
 
![](/images/data/split-result.png)

---

## Saving Data

Data tables can be saved as comma separated value (csv) text files by clicking the `Save All` or `Save View` buttons in the data table sidebar.

* `Save All`: saves the original data, disregarding any active data filter settings.
* `Save View`: saves the data as currently displayed. Data hidden from view are not saved and cannot be retrieved from the saved file.  