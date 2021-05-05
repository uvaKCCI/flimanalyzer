# Data Files

The FLIMAnalyzer software processes data provided in text files organized in spreadsheet format. Data can be loaded from a single text file or imported and concatenated from a series of individual files through the `Files` menu or application toolbar. 

| Tool Icon             |  File Operation | Description
|:-------------------------:|:-------------------------:|:-----:|
|![](/images/files/open.png)  | [Open Data File](#open-data-file) | Opens a single text file. All columns are retained as-is.
|![](/images/files/import.png)  | [Import Data Files](#import-data-files) | Imports as one or multiple text files. Additional column values can be parsed from raw data files names, columns may be renamed or dropped.

## Open Data File

Follow these steps to open a single text file. The data is expected to be organized in spreadsheet format, each line representing a data row and column values in each line separated by specific delimiting characters. Common formats are .csv files using `,` as delimiting character.  However other column delimiters are allowed as well, see below.

1. Go to `File > Open` or click on the `Open File` icon on the far left of the application toolbar.
2. In the `Open File` dialog window, check the appropriate column value delimiting character, e.g.  `,`,`;`,`<tab>`,`<space>`, or enter a character sequence in the `Others` text field.
3. Click `Open` and choose the data text file to open.
4. The data will be read from the selected file as-is and presented in a table window in spreadsheet format. The column headers correspond to values of the first row in the data text file. 

![](/images/files/open-dlg.png)

## Import Data Files

The `File > Import` menu function and `Import Files` toolbar icon (second from the left in toolbar) provide more flexibility for configuration of data loads. The data is expected to be organized in text files in spreadsheet format as described above. 

Additional configurable options for the `File Import` function:

* Concatenation of multiple text files into a single data table, 
* parsing of data text filenames that can be added as additional column values to the final table,
* dropping of columns based on column headers (parsed from first line of text files),
* and renaming of column headers.

1. Go to `File > Import` or click on the `Import File` icon (second from the left of the application toolbar.
2. In the `Import File` dialog window, check the appropriate column value delimiting character, e.g.  `,`,`;`,`<tab>`,`<space>`, or enter a character sequence in the `Others` text field. This is the same as for the `Open File` function.
3. **Optional:** Choose a parser from the dropdown menu.  Selection of `no_parser` means that filenames will be ignored for parsing of any additional data. When choosing a specific parser, the content in the `Parse from Filenames` table changes, see (4).
4. **Optional:** Select/Deselect `Use` checkbox to parse/ignore labels from the name of each filename. Adjust the `Catgeory` value which will be used as column header to collect the parsed label, and modify the `Regex` expression used to extract the desired filename portion. 

    **Example:** Choosing the built-in `fov_treatmnent_cell` parser will extract the following values for `FOV`, `Treatment`, `Cell` from a group of data files and these values to the imported data table:

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