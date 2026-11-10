# Loading Data

FLIMAnalyzer reads data from text files laid out like a spreadsheet. You can open a single text file, or import several files and combine them into one table. Both are available in the `File` menu and in the tool panel.

| Tool Icon |  File Operation | Description |
|:---------:|:---------------:|:-----------:|
|![](/images/files/open.png)  | [Open Data File](#open-data-file) | Opens a single text file. The columns are kept as they are. |
|![](/images/files/import.png)  | [Import Data Files](#import-data-files) | Imports one or more text files. Values for extra columns can be<br> read from the file names, and columns can be renamed or dropped. |

## Open Data File

The file must be laid out like a spreadsheet: each line is a data row, and the values in a line are separated by a delimiter character. A common format is the .csv file, which uses `,` as the delimiter. Other delimiters can be used as well (see step 2). Follow these steps to open a single text file:

1. Go to `File` > `Open...` or click the `Open file` icon, the first icon in the tool panel.
2. In the `Open File` dialog, check the delimiter used in the file: `Comma`, `Semicolon`, `Tab` or `Space`. For any other delimiter, enter its characters in the `Others:` field. By default, `Tab` and `Comma` are checked.
3. Click `Open` and choose the data text file to open.
4. FLIMAnalyzer reads the data and shows them in a table window. The column headers are taken from the first line of the file. Three text columns are added: `Source`, the file as a URI (for example `file:///data/9SR/Results-a-Dox15_01.txt`), `Directory`, the folder of the file, and `File`, its name. A column the file already has is kept as it is and not added again, so a table saved by FLIMAnalyzer keeps the `Source` of the files it was made from.

![](/images/files/open-dlg.png)

## Import Data Files

`File` > `Import...` and the `Import files` icon (the second icon in the tool panel) give you more options for loading data. The files must be laid out as described above.

In addition to opening files, the import can:

* combine several text files into a single data table,
* read values from the file names and add them to the table as extra columns,
* drop columns by their headers (taken from the first line of the files),
* and rename column headers.

1. Go to `File` > `Import...` or click the `Import files` icon.
2. In the `Import File(s)` dialog, check the delimiter used in the files: `Comma`, `Semicolon`, `Tab` or `Space`. For any other delimiter, enter its characters in the `Others:` field. This works the same as in the `Open File` dialog.
3. **Optional:** Choose a parser from the `Filename Parser` list. With `no_parser`, no values are read from the file names. When you choose a parser, the `Parse from Filenames` table changes (see step 4).
4. **Optional:** In the `Parse from Filenames` table, check `Use` for each value to read from the file names, and uncheck it for values to ignore. The `Category` column sets the header of the new table column for each value. The `Regex` column holds the pattern (a regular expression) that finds the value in the file name. Change both as needed.

    **Example:** The built-in `fov_treatment_cell_parser` reads the following values for `FOV`, `Treatment` and `Cell` from the file names and adds them to the imported data table. As with `Open`, the `Source`, `Directory` and `File` columns are added too (`Source` and `Directory` are not shown here):

    | File | FOV | Treatment | Cell |
    |:----:|:---:|:---------:|:----:|
    | Results-a-ctrl-1 | a | ctrl | 1 |
    | Results-a-ctrl-2 | a | ctrl | 2 |
    | Results-b-ctrl-1 | b | ctrl | 1 |
    | Results-b-ctrl-2 | b | ctrl | 2 |

5. **Optional:** In the `Rename Columns` table, enter how column headers are renamed. **Each entry replaces matching text anywhere in a column header, not only whole headers.** To rename nothing, remove all values in the first column. These are the settings of the [Rename Columns](/userguide/data/rename.md) tool.
6. **Optional:** In the `Drop Columns` table, enter the columns to drop from the data, one per line. **Note: A column is dropped if its header contains an entry anywhere, not only if the whole header matches.** These are the settings of the [Drop Columns](/userguide/data/drop.md) tool; an entry that has another match there (for example `ends with`) keeps it.

7. Click `Add Files` to select one or more files to import. **Data from all listed files will be concatenated into a single data table.** Select individual files in the list and click `Remove Files` to remove them from the list. Click `Reset` to clear the file list.
8. Click `Import`. FLIMAnalyzer reads the listed files and stacks them into a single data table, then renames and drops columns as set in steps 5 and 6. It then adds the calculated columns of the [Calculate](/userguide/data/calculate.md) tool's settings, for example `NAD(P)H tm` and `FLIRR`. The files should all have the same column headers (the first line of each file).

![](/images/files/import-dlg.png)

After [opening](#open-data-file) or [importing](#import-data-files) files, the data are shown in a table window. Some columns become category columns: columns with values read from the file names, and columns with one of the names FLIMAnalyzer knows as categories, such as `Treatment`, `FOV`, `Cell`, `Cell line`, `Well`, `Time` or `Compartment`. A category column has a small, usually fixed, set of possible values, such as treatment names. Category column headers have a light blue background. All other column headers have a gray background. Other text columns, such as `Source`, `Directory` and `File`, are not category columns: they can't be used to group or filter the data.

## The Source column

`Source` records where each row comes from: its file, as a URI. It replaces `Directory` and `File`, which are still added in this version but will be removed in a later one. To add `Source` to a table imported with FLIMAnalyzer 0.6 or earlier, use [Directory/File to Source](source.md).

`Import...` always writes its own `Source`, `Directory` and `File` columns. If a data file already has a column with one of these names, that column is renamed, by default to `<name> (before Import)`, for example `Source (before Import)`; a number is added if that name is taken too. The run summary and the log list the renamed columns. A category column read from the file names (for example `FOV`) replaces a column of the same name in the file, with a warning. In settings files and workflow files, the Import tool's `clash_name` sets the template (`{name}` is the column's name, `{tool}` the tool's short name) and `clash_renames` sets the new name of single columns.

![](/images/data/dataframe.png)