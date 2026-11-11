# Loading Data

FLIMAnalyzer reads data from text files laid out like a spreadsheet: each line is a data row, and the values in a line are separated by a delimiter, by default a tab or a comma (`.txt` and `.csv` files). You can open files as they are, or import them: read them and run a workflow on them that renames, drops and calculates columns, takes categories from the file names and joins the files into one table. Both are in the `File` menu and in the tool panel.

| Tool Icon |  File Operation | Description |
|:---------:|:---------------:|:-----------:|
|![](/images/files/open.png)  | [Open Data Files](#open-data-files) | Opens text files, each in a table window of its own. The columns are kept as they are. |
|![](/images/files/import.png)  | [Import Data Files](#import-data-files) | Reads text files and runs a workflow on them, for example to<br> combine them into one table with categories from the file names. |

## Open Data Files

1. Go to `File` > `Open...` or click the `Open file` icon, the first icon in the tool panel.
2. Choose one or more data files and click `Open`.
3. FLIMAnalyzer reads each file into a table window of its own. The column headers are taken from the first line of the file. Three text columns are added first: `Source`, the file as a URI (for example `file:///data/9SR/Results-a-Dox15_01.txt`), `Directory`, the folder of the file, and `File`, its name. The other columns stay in the order of the file. A file that can't be read is listed in a message; the others are opened.

## Import Data Files

`File` > `Import...` (or the `Import files` icon, the second icon in the tool panel) reads files and runs a [workflow file](/userguide/workflows.md#workflow-files) on them. The workflow file decides everything that is done with the data, so the same files and the same workflow always give the same table, also in [batch mode](/userguide/batch).

1. Go to `File` > `Import...` or click the `Import files` icon.
2. Choose one or more data files and click `Open`.
3. Choose the workflow to run. The workflow you used last is preselected. The built-in ones:
    - `Import`: renames the channels' columns (for example `Exc1_-Ch2-_t1` to `NAD(P)H t1`, see [Rename Columns](rename.md)), drops the other channels' columns ([Drop Columns](drop.md)), joins the files into one table and adds the calculated FLIM features ([Calculate](calculate.md)). This is what `Import...` did up to FLIMAnalyzer 0.6 with the default settings.
    - `Import: FOV, Treatment, Cell` and the other `Import: ...` workflows: the same, and then they take these categories from the file paths, as the filename parsers of FLIMAnalyzer 0.6 did (a [Separate Categories](separate.md) step on `Source`). For example, `Import: FOV, Treatment, Cell` reads `FOV` `a`, `Treatment` `ctrl` and `Cell` `1` from `Results-a-ctrl-1.txt`.
    - Your own workflow files, for example a copy of a built-in one with other patterns (see [Workflow files](/userguide/workflows.md#workflow-files)).
4. FLIMAnalyzer shows the workflow's steps. Click `Run`.
5. The files are read (as a workflow file's `read` section says) and the workflow runs on them. A window opens for each result that no later step of the workflow uses, for example the joined table of `Import`. Results that the workflow saves open as saved; the run summary shows where.

If a run would open more windows than the app setting `max_windows` allows (by default 10 tables, 10 plots and 4 images), for example a workflow without a step that joins the tables run on 300 files, it doesn't start, and a message suggests running it with `flimbatch` or adding a step that joins the tables, such as `Concatenate`.

To run a workflow file on a table that is already open, for example after reshaping it with the table tools, use `Workflow` > `Run Workflow File...`. The workflow files found in the workflow search path are also listed in the `Workflow` menu; there they run on the tables you select in their dialog.

After [opening](#open-data-files) or [importing](#import-data-files) files, the data are shown in a table window. Some columns become category columns: columns with values taken from the file names by a workflow, and columns with one of the names FLIMAnalyzer knows as categories, such as `Treatment`, `FOV`, `Cell`, `Cell line`, `Well`, `Time` or `Compartment`. A category column has a small, usually fixed, set of possible values, such as treatment names. Category column headers have a light blue background. All other column headers have a gray background. Other text columns, such as `Source`, `Directory` and `File`, are not category columns: they can't be used to group or filter the data.

## The Source column

`Source` records where each row comes from: its file, as a URI. It replaces `Directory` and `File`, which are still added in this version but will be removed in a later one. To add `Source` to a table imported with FLIMAnalyzer 0.6 or earlier, use [Directory/File to Source](source.md).

When a file is read, its own `Source`, `Directory` or `File` column is kept: a table saved by FLIMAnalyzer keeps the `Source` of the files it was made from, and no other `Source` is added. A `Source` column whose values are not URIs (for example a column the measurement software wrote) is renamed `Source (before Read)` instead, and FLIMAnalyzer's own `Source` is added; the message after reading lists the renamed columns. A workflow file's `read` section can set `"existing": "rename"` to rename all three columns.

![](/images/data/dataframe.png)