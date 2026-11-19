# Loading Data

FLIMAnalyzer reads data from text files laid out like a spreadsheet: each line is a data row, and the values in a line are separated by a delimiter, by default a tab or a comma (`.txt` and `.csv` files). You can open files as they are, or import them: read them and run a workflow on the tables, for example one that renames, drops and calculates columns, takes categories from the file names and joins the tables into one. Both are in the `File` menu and in the tool panel.

| Tool Icon |  File Operation | Description |
|:---------:|:---------------:|:-----------:|
|![](/images/files/open.png)  | [Open Tables](#open-tables) | Opens text files, each in a table window of its own. The columns are kept as they are. |
|![](/images/files/import.png)  | [Import Tables](#import-tables) | Reads text files and runs a workflow on the tables, for example to<br> combine them into one table with categories from the file names. |

## Open Tables

1. Go to `File` > `Open Tables...` or click the `Open Tables` icon, the first icon in the tool panel.
2. Choose one or more data files and click `Open`.
3. FLIMAnalyzer reads each file into a table window of its own. The column headers are taken from the first line of the file. Three text columns are added first: `Source`, the file as a URI (for example `file:///data/9SR/Results-a-Dox15_01.txt`), `Directory`, the folder of the file, and `File`, its name. The other columns stay in the order of the file. A file that cannot be read is listed in a message; the others are opened.

The files are read with the settings of the `Open Tables` tool (see [Read settings](#read-settings)). It has no dialog: to change its settings, use an app settings file with an `Open Tables` section in `tools` (see [Settings](/userguide/settings)).

## Import Tables

`File` > `Import Tables...` (or the `Import Tables` icon, the second icon in the tool panel) reads files, one table per file, and runs a [workflow file](/userguide/workflows.md#workflow-files) on the tables. The workflow decides what is done with the tables, so the same files, read settings and workflow always give the same results, also in [batch mode](/userguide/batch).

1. Go to `File` > `Import Tables...` or click the `Import Tables` icon.
2. Choose one or more data files and click `Open`.
3. The `Import Tables` dialog shows how the files are read (see [Read settings](#read-settings)) and, under `Workflow`, the workflow to run on the tables. The dialog keeps your choices for the next time. The list shows the workflow files with the category `["File", "Import"]`, the workflow files of `File` > `Import` (all workflow files if none has this category, see [Workflow files](/userguide/workflows.md#workflow-files)):
    - `None (open the tables)`, the first entry and the default: no workflow; each table opens in a window, as with `Open Tables`.
    - `Import`: renames the channels' columns (for example `Exc1_-Ch2-_t1` to `NAD(P)H t1`, see [Rename Columns](rename.md)), drops the other channels' columns ([Drop Columns](drop.md)), joins the tables into one and adds the calculated FLIM features ([Calculate](/userguide/analysis/calculate.md)). This is what `Import...` did up to FLIMAnalyzer 0.6 with the default settings. `Import` saves the joined table with the calculated features (see [Results of a workflow file](/userguide/workflows.md#results-of-a-workflow-file)). Files without these channels' columns, for example files of one channel with columns such as `_t1`, are joined as they are; the run summary lists the calculations that were skipped.
    - Your own workflow files, for example a copy of `Import` with a Separate Categories step that takes categories from the file names (see [Workflow files](/userguide/workflows.md#workflow-files)).
    - `Other Workflow File...`, the last entry: choose any workflow file, also one with another category or outside the workflow search path.
4. Click `OK`. With a workflow, FLIMAnalyzer shows its steps; click `Run`.
5. The files are read, one task per file, and the workflow runs on the tables. A window opens for each result that no later step of the workflow uses, for example the joined table of `Import`. Results that the workflow saves open as saved; the run summary shows where.

**Categories from the file names:** after importing with `Import`, use [Separate Categories](separate.md) with one of its presets, the filename parsers of FLIMAnalyzer 0.6 (for example `FOV, Treatment, Cell`), on the `Source` column. To have them in every import, add such a step to your own copy of `Import` (see [Presets](separate.md#presets)).

Before the run, the workflow's steps are validated against the first 20 rows of each file. If a run would open more windows than the app setting `max_windows` allows (by default 10 tables, 10 plots and 4 images), for example a workflow without a step that joins the tables run on 300 files, it does not start, and a message suggests running it with `flimbatch` or choosing a workflow that joins the tables, for example with `Concatenate`.

To run a workflow file on a table that is already open, for example after reshaping it with the table tools, use `Workflow` > `Run Workflow File...`. The workflow files found in the workflow search path are also listed in the menus, in the menu and submenu that their `category` names (the built-in `Import` in `File` > `Import`, files without `category` in the `Workflow` menu, see [Workflow files](/userguide/workflows.md#workflow-files)); there they run on the tables you select in their dialog.

## Read settings

`Open Tables` and `Import Tables` each have these settings, saved like the settings of any tool:

* `Column delimiters`: each of these characters separates columns. A tab is shown and typed as `\t`. Default: `\t,`, a tab or a comma.
* `Files to include`: in folders (given with `-i`, or to `flimbatch`), the files with these extensions, separated by commas. Default: `.txt, .csv`. Files you choose one by one are read whatever their extension.
* `Text encoding`: the files' text encoding, for example `utf-8` (the default) or `latin-1`.
* `Files to exclude`: file names without folder that are not read, separated by commas, for example `Results_old.txt`.
* `File's own Source, Directory, File`: what happens to a file's own `Source`, `Directory` or `File` column: `keep` (the default) or `rename` (see [The Source column](#the-source-column)).
* `Name of renamed column`: the new name of such a column. Default: `{name} (before {tool})`, for example `Source (before Read)`.

After [opening](#open-tables) or [importing](#import-tables) files, the data are shown in a table window. Some columns become category columns: columns with values taken from the file names by a workflow, and columns with one of the names FLIMAnalyzer knows as categories, such as `Treatment`, `FOV`, `Cell`, `Cell line`, `Well`, `Time` or `Compartment`. A category column has a small, usually fixed, set of possible values, such as treatment names. Category column headers have a light blue background. All other column headers have a gray background. Other text columns, such as `Source`, `Directory` and `File`, are not category columns: they cannot be used to group or filter the data.

## The Source column

`Source` records where each row comes from: its file, as a URI. It replaces `Directory` and `File`. They are still added in this version and are removed in 0.8.0. To add `Source` to a table imported with FLIMAnalyzer 0.6 or earlier, use [Directory/File to Source](source.md).

When a file is read, its own `Source`, `Directory` or `File` column is kept: a table saved by FLIMAnalyzer keeps the `Source` of the files it was made from, and no other `Source` is added. A `Source` column whose values are not URIs (for example a column the measurement software wrote) is renamed `Source (before Read)` instead, and FLIMAnalyzer's own `Source` is added; the message after reading lists the renamed columns. The read setting `File's own Source, Directory, File` set to `rename` renames all three columns.

![](/images/data/source-columns.png)