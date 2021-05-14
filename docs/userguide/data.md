# Data Tables

## Loading Data

The FLIMAnalyzer software processes data provided in text files organized in spreadsheet format. Data can be loaded from a single text file or imported and concatenated from a series of individual files through the `Files` menu or application toolbar. 

| Tool Icon |  File Operation | Description |
|:---------:|:---------------:|:-----------:|
|![](/images/files/open.png)  | [Open Data File](#open-data-file) | Opens a single text file. All columns are retained as-is. |
|![](/images/files/import.png)  | [Import Data Files](#import-data-files) | Imports one or multiple text files. Additional column values can be<br> parsed from raw data files names, columns may be renamed or dropped. |

### Open Data File

Follow these steps to open a single text file. The data is expected to be organized in spreadsheet format, each line representing a data row and column values in each line separated by specific delimiting characters. Common formats are .csv files using `,` as delimiting character.  However other column delimiters are allowed as well, see below.

1. Go to `File > Open` or click on the `Open File` icon on the far left of the application toolbar.
2. In the `Open File` dialog window, check the appropriate column value delimiting character, e.g.  `,`,`;`,`<tab>`,`<space>`, or enter a character sequence in the `Others` text field.
3. Click `Open` and choose the data text file to open.
4. The data will be read from the selected file as-is and presented in a table window in spreadsheet format. The column headers correspond to values of the first row in the data text file. 

![](/images/files/open-dlg.png)

### Import Data Files

The `File > Import` menu function and `Import Files` toolbar icon (second from the left in toolbar) provide more flexibility for configuration of data loads. The data is expected to be organized in text files in spreadsheet format as described above. 

Additional configurable options for the `File Import` function:

* Concatenation of multiple text files into a single data table, 
* parsing of data text filenames that can be added as additional column values to the final table,
* dropping of columns based on column headers (parsed from first line of text files),
* and renaming of column headers.

1. Go to `File > Import` or click on the `Import File` icon (second from the left of the application toolbar.
2. In the `Import File` dialog window, check the appropriate column value delimiting character, e.g.  `,`,`;`,`<tab>`,`<space>`, or enter a character sequence in the `Others` text field. This is the same as for the `Open File` function.
3. **Optional:** Choose a parser from the dropdown menu.  Selection of `no_parser` means that filenames will be ignored for parsing of any additional data. When choosing a specific parser, the content in the `Parse from Filenames` table changes, see (4).
4. **Optional:** Select/Deselect `Use` checkbox to parse/ignore identifiers from the name of each file. Adjust the values in the `Category` column which will be used as new column headers for the parsed file identifiers, and modify the `Regex` expression used to extract the desired filename portion. 

    **Example:** Choosing the built-in `fov_treatmnent_cell` parser will extract the following values for `FOV`, `Treatment`, `Cell` from a group of data files and adds these values to the imported data table:

    | File | FOV | Treatment | Cell |
    |:----:|:---:|:---------:|:----:|
    | Results-a-ctrl-1 | a | ctrl | 1 |
    | Results-a-ctrl-2 | a | ctrl | 2 |
    | Results-b-ctrl-1 | b | ctrl | 1 |
    | Results-b-ctrl-2 | b | ctrl | 2 |

5. **Optional:** In the `Rename` table, specify renaming convention for column headers. **These values specify substitution patterns with implicit `\*` wildcards that replace all matching substrings.** Remove all values in columns 1 if no renaming is desired.
6. **Optional:** In the `Drop Columns` table, specify columns that should be dropped from the data. **Note: These values specify patterns with implicit `\*` wildcards that apply to column headers with matching substrings.**

8. Click `Add` to select a single or multiple files to import. **Data from all listed files will be concatenated into a single data table.** Select indiividual files in the list and click `Remove` to remove specific files from the list. Click `Reset` to clear the file list.
8. Click `Import`. The data will be read from the selected files, processed and concatenated vertically into a single data table. It is assumed that the column headers in each data file (i.e. the first row in each file) have matching values. 

![](/images/files/import-dlg.png)

After [opening](#open-data-file) or [importing](#import-data-files) files, the data are displayed in a spreadsheet window, aka a data table. Columns containing text or information parsed from filenames during import are specified as categorical data columns. They have limited, and usually fixed, number of discrete possible values. Headers of categorical columns have a light blue background; all other column headers are displayed with a gray background.

![](/images/data/dataframe.png)

--- 

## Adjusting Precision

The `Precision` control field in each data table window sets the number of decimal places displayed for non-integer numbers.  For example, a precision value of `3` means that non-integer numbers are displayed with three decimal places.

![](/images/data/precision.png)

**Note:** Changing of the `Precision` value changes the displayed number but the underlying raw data number remains unchanged. 

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

Let's say we're interested in the trend of `FAD a1[%]` and `NAD(P)H a2[%]` for each cell. Looking at the original data, it is hard to see the trend for select measurements in each cell across the treatment time axis. Pivoting the treatment column and summarizing the measurements (mean aggregates) for each cell in each FOV and compartment can help with the exploration of trends over the treatment time series.

1. In the sidebar of the data table, click the `Pivot` button.

2. In the `Pivot Data` dialog window, select the `Treatment` option. Leave the other options deselected. **Note:** The window will show all categorical column headers as selectable options.

    ![](/images/data/pivot-input.png)

3. Click `Ok`.

4. In the next dialog window, select the numeric columns of interest, e.g. `FAD a1[%]` and `NAD(P)H a2[%]` for this example.

    ![](/images/data/pivot-columns.png)

5. Click `Ok`.

The resulting table looks like the one below. Note how each row now shows the **summarized (mean) value** for a given `Cell`, `Compartment`, `FOV`. The values of the original `Treatment` column were rearranged (pivoted) into separate columns such that each row now shows the trend across `Treatment` groups for the two selected measurements, e.g. `FAD a1[%] Ctrl` through `FAD a1[%] Dox60` and `NAD(P)H a2[%] Ctrl` through `NAD(P)H a2[%] Dox60`.

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