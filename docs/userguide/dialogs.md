# Tool dialogs

Every tool and workflow opens a configuration dialog, titled `Configuration: <tool name>`, for example `Configuration: Summarize`. The controls below are the same in all of them. The pages of the tools describe only their own settings.

A tool needs data: if no table window is open, the GUI says "Open or import data first." instead of opening the dialog.

## Choosing the data

At the top of the dialog, a line of text says what the tool does. Below it, you choose the table the tool runs on. The list has all open table windows, by their window titles. The table window that was last in front is first in the list and is selected.

Most tools have one choice, `Data`. Some have more:

* `Merge` has `Left` and `Right`.
* `Concatenate` has `Tables`, a list with a check box for each open table.
* `FLIM Feature Analysis` has `Training data` and `Data`.

When you choose another table, the dialog lists the columns of that table, for example under `Grouping` and `Features`.

## Result prefix

`Result prefix` is text that is put in front of the names of the tool's results. Leave it empty for no prefix. For example, with the prefix `A-`, the `Summarize` tool makes the table `A-Table: Summary` instead of `Table: Summary`. A prefix keeps the results of several runs of the same tool apart. Workflow dialogs have no `Result prefix`: the steps of a workflow name their own results.

## Saving results

At the bottom of the dialog, `Save results in` and the folder next to it set whether and where the results are saved as files. Check `Save results in`, then type a folder or click the button next to it to choose one. The folder is created if it doesn't exist yet. By default, it is the folder `FLIMAnalyzerResults` in your home folder.

The results are saved in a new folder for each run, named after the date and time of the run, for example `2026-11-03_14-05-31`. In it, the results of the tool are in a folder named after the tool, for example `Summarize`:

* figures as `.png` files,
* tables as `.txt` files (comma-separated, with the row numbers in the first column),
* other results as files in Python's pickle format,
* and the folder `pickled`, with all results of the tool except the figures in one file in Python's pickle format.

The file names are made from the result names; characters that can't be used in file names are replaced, for example `Table: Summary` becomes `Table_Summary.txt`. The folder of the run also gets a file `run_summary.txt`. It lists when the run started and finished, and the status and message of each task.

Results are also shown in their own windows, whether they are saved or not. Workflows always save their results, in a folder of their own; there, `Save results in` can't be unchecked (see [Workflows](/userguide/workflows)).

While a tool runs with `Save results in` checked, the progress dialog shows the results folder. If you cancel a run while `Save results in` is unchecked, the run summary says "No results were saved because Autosave is off." (see [The run summary](/userguide/workflows.md#the-run-summary)).

## Loading and saving settings

`Load Settings...` reads the tool's settings from a settings file, and `Save Settings...` adds the tool's current settings to a settings file. The settings include whether the results are saved, and to which folder. See [The settings of a tool](/userguide/settings.md#the-settings-of-a-tool).

## Features

Many tools have a `Features` list with the numeric columns of the table. Check the features the tool uses. They are used in the order of the columns in the table, not in the order you check them. `Select All` and `Deselect All` check or uncheck all features.

Most tools also have an `All features` check box above the list. With it, the tool uses all numeric columns of the table, also with another table that has other columns. While it is checked, the list shows all features checked and can't be changed. Some tools don't offer `All features`:

* `Autoencoder: Train`.
* `Frequency Histogram`: it has a table with a row for each feature instead of the list.
* `Pair Plot` and `FLIRR Plot`: they have their own fields for the columns to plot.
* The workflows: they have their own list of features.

If the settings name features that the selected table doesn't have, a note above the list names them. They are checked again when you choose a table that has them.

## Resources

Some tools have a `Resources` section. It is collapsed; click `Resources` to open it.

![](/images/dialogs/tool-dialog.png)

* `Threads`: how many threads the tool uses for its calculations. `-1` (the default) uses all CPU cores available to the tool. `0` is not allowed. `K-Means`, `Random Forest`, the autoencoder tools and the autoencoder workflows have this setting.
* `Device`: which processor does the calculations, for example a GPU. The autoencoder tools (`Autoencoder: Train`, `Autoencoder: Run`, `Autoencoder: Augment Data`) and the workflows `FLIM Data Augmentation Tuning` and `FLIM Feature Analysis` have this setting. See [Using a GPU](/install/index.md#using-a-gpu).

The other tools have no `Resources` section; they use one thread on the CPU.

## Help and errors

Hover the mouse over the name of a field to see a short help text.

The dialog checks the settings while you change them:

* A field with an error is marked with an error sign. Hover the mouse over the sign to see the message. In lists and tables, the sign is in the row with the error.
* A warning sign marks a setting that works but may not be what you want, for example a column that a workflow guessed (see [Workflows](/userguide/workflows.md#checking-the-settings)).
* Messages that are not about a single field, for example about the folder under `Save results in`, are shown in red text above `Save results in`.

`OK` stays disabled while there are errors. Fix them, and `OK` becomes available.

## Hidden settings

A field that allows only one value with the current settings is hidden. It appears again when other settings allow more values. For example, the plot dialogs show `Single figure` only for some numbers of grouping columns.

## Last settings used

When you click `OK`, the GUI keeps the settings of the dialog. The next time you open the same tool, its dialog opens with these settings, including the result prefix and the folder under `Save results in`. `Cancel` keeps the settings that were there before.

These settings are kept only while FLIMAnalyzer is open; they are not saved when it closes. To keep them, use `File` > `Export Settings...` or `Save Settings...` (see [Settings](/userguide/settings)).

## Result windows

Each table and plot that a tool makes opens in its own window. The window title is the type of the result and its name, for example `Table: Summary`, or `Plot: <name>` for a plot. If a window with that title is already open, a number is added, for example `Table: Summary-1`. The [`Window` menu](/userguide/appmenu.md#window) lists all windows.

Workflows don't open windows for their results. Their results are saved in the results folder (see [Workflows](/userguide/workflows)).

While a tool runs, a progress dialog shows its tasks (see [The progress dialog](/userguide/workflows.md#the-progress-dialog)).
