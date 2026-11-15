# Tool dialogs

Every tool and workflow opens a configuration dialog, titled `Configuration: <tool name>`, for example `Configuration: Summarize`. The controls below are the same in all of them. The pages of the tools describe only their own settings.

Every tool dialog has three sections, one under the other:

* `Input`: the data the tool runs on (see [Choosing the data](#choosing-the-data)).
* `Settings`: the tool's settings, with `Load Settings...` and `Save Settings...` (see [Loading and saving settings](#loading-and-saving-settings)).
* `Output`: what names the results and how they are saved: `Result prefix` (see [Result prefix](#result-prefix)) and `Save results` with the formats (see [Saving results](#saving-results)).

A tool needs data: if no table window is open, the GUI says "Open or import data first." instead of opening the dialog.

## Choosing the data

At the top of the dialog, a line of text says what the tool does. Below it, in the `Input` section, you choose the table the tool runs on. The list has all open table windows, by their window titles. The table window that was last in front is first in the list and is selected.

Most tools have one choice, `Data`. Some have more:

* `Merge` has `Left` and `Right`.
* `Concatenate` has `Tables`, a list with a check box for each open table.
* `FLIM Feature Analysis` has `Training data` and `Data`.

When you choose another table, the dialog lists the columns of that table, for example under `Grouping` and `Features`. The dialog offers only the columns the selected table has.

## Result prefix

`Result prefix` is text that is put in front of the names of the tool's results. Leave it empty for no prefix. For example, with the prefix `A-`, the `Summarize` tool makes the table `A-Table: Summary` instead of `Table: Summary`. A prefix keeps the results of several runs of the same tool apart. Workflow dialogs have no `Result prefix`: the steps of a workflow name their own results.

## Saving results

In the `Output` section, check `Save results` to save the results as files. The folder and the formats below it can only be changed while it is checked; unchecking it keeps them for the next time. The folder is created if it doesn't exist yet.

* `Use the default folder` (checked unless the tool has a folder of its own): the tool saves in the default results folder, shown greyed in the `Folder` field. This is the results folder of the settings (`results_dir`, or `-o` on the command line); if that is not set, the folder FLIMAnalyzer was started from (see [Settings](/userguide/settings.md#layout-of-a-settings-file)). The tool keeps following the default when it changes.
* Uncheck it to give the tool a folder of its own: type a folder, or click the button next to it to choose one. The field starts with the default folder if the tool has no folder of its own yet. Checking and unchecking `Use the default folder` switches the field between the default folder and the tool's own folder; the dialog remembers the tool's own folder only while it is open.
* A line below says how the tool's folder is kept. If a results folder is set (`results_dir`, `-o` or `Make Default Folder`), a folder inside it is kept relative to it, for example `kmeans` for `<default folder>/kmeans`: if the default folder changes, the tool saves in `kmeans` inside the new default folder. Any other folder is kept as it is, also a folder inside the start folder when no results folder is set, because the start folder can differ from one session to the next. Choosing the default folder itself is the same as checking `Use the default folder`.
* `Make Default Folder` (only for a folder of the tool's own that isn't the default yet) makes the folder the default results folder, saved in the user settings file. Every tool that uses the default folder saves there from then on; tools with a folder of their own keep it.

Below the folder, the `Output` section has a column for each kind of result the tool makes, with the formats to save it in and their options. You can check several formats of one kind; each kind needs at least one:

* `Tables`: `tsv`, tab-separated text with the extension `.txt` (default), and `csv`, comma-separated text (`.csv`). Tables are saved without the row numbers.
* `Plots`: `png` (default), `svg` and `pdf`. `Resolution (dpi)` applies to `png`; the default is 300 dpi.

The tool's dialog keeps the formats you chose, with its other settings.

The results are saved in a new folder for each run, named after the date and time of the run, for example `2026-11-03_14-05-31`. If another run started in the same second, for example a second `flimbatch` job with the same output folder, the folder gets `-2`, `-3` and so on added. In it, the results of the tool are in a folder named after the tool, for example `Summarize`:

* tables and plots in the formats chosen,
* other results as files in Python's pickle format,
* and the folder `pickled`, with all results of the tool except the figures in one file in Python's pickle format.

The file names are made from the result names; characters that can't be used in file names are replaced, for example `Table: Summary` becomes `Table_Summary.txt`. The folder of the run also gets a file `run_summary.txt`. It lists when the run started and finished, the settings files used (see [Settings files from older versions](/userguide/settings.md#settings-files-from-older-versions)), and the status and message of each task. A task's message is also how a tool reports a warning: the task is completed, but something in the data needs attention (for example, `Concatenate` pairing rows that don't match). The GUI shows such warnings after the run.

Results of tools are also shown in their own windows, whether they are saved or not. Workflows always save their results, in a folder of their own; there, `Save results` can't be unchecked (see [Workflows](/userguide/workflows)). A workflow file saves only the results of the steps marked `save` (see [Results of a workflow file](/userguide/workflows.md#results-of-a-workflow-file)).

While a tool runs with `Save results` checked, the progress dialog shows the results folder. If you cancel a run while `Save results` is unchecked, the run summary says "No results were saved because Save results is off." (see [The run summary](/userguide/workflows.md#the-run-summary)).

## Loading and saving settings

`Load Settings...` reads the tool's settings from a settings file, and `Save Settings...` adds the tool's current settings to a settings file. The settings include whether the results are saved, and to which folder. See [The settings of a tool](/userguide/settings.md#the-settings-of-a-tool).

## Features

Many tools have a `Features` list with the numeric columns of the table. Check the features the tool uses. They are used in the order of the columns in the table, not in the order you check them. `Select All` and `Deselect All` check or uncheck all features.

Most tools also have an `All features` check box above the list. With it, the tool uses all numeric columns of the table, also with another table that has other columns. While it is checked, the list shows all features checked and can't be changed. Some tools don't offer `All features`:

* `Autoencoder: Train`.
* `Frequency Histogram`: it has a table with a row for each feature instead of the list.
* `Pair Plot` and `FLIRR Plot`: they have their own fields for the columns to plot.
* The workflows: they have their own list of features.

If the settings name features that the selected table doesn't have, a note above the list names them. They are validated again when you choose a table that has them.

## Resources

Some tools have a `Resources` section. It is collapsed; click `Resources` to open it.

![](/images/dialogs/tool-dialog.png)

* `Threads`: how many threads the tool uses for its calculations. `-1` (the default) uses all CPU cores available to the tool. `0` is not allowed. `K-Means`, `Random Forest`, the autoencoder tools and the autoencoder workflows have this setting.
* `Device`: which processor does the calculations, for example a GPU. The autoencoder tools (`Autoencoder: Train`, `Autoencoder: Run`, `Autoencoder: Augment Data`) and the workflows `FLIM Data Augmentation Tuning` and `FLIM Feature Analysis` have this setting. See [Using a GPU](/install/index.md#using-a-gpu).

The other tools have no `Resources` section; they use one thread on the CPU.

## Help and errors

Hover the mouse over the name of a field to see a short help text.

The dialog validates the settings while you change them:

* A field with an error is marked with an error sign. Hover the mouse over the sign to see the message. In lists and tables, the sign is in the row with the error.
* A warning sign marks a setting that works but may not be what you want, for example a column that a workflow guessed (see [Workflows](/userguide/workflows.md#validating-the-settings)).
* Messages that are not about a single field, for example about the folder under `Save results`, are shown in red text above the `Output` section.
* Some tools also validate the values of the table, not only its columns, for example `Separate Categories`: values that can't be separated as set are a warning at the field.

`OK` stays disabled while there are errors. Fix them, and `OK` becomes available.

Some tools show an example below the `Settings` section: a small table with a few rows of the selected table, and the columns the tool makes from them, marked `→`, for example `→ FOV:Cell`. It changes as you change the settings, so you can check the result before you run the tool. These tools are `Fuse Categories`, `Separate Categories`, `Rename Columns`, `Drop Columns`, `Calculate`, `Directory/File to Source`, `Pivot`, `Unpivot`, `Scale` and `Categorize Data`.

Most tools need at least one feature selected under `Features`; `PCA`, `Scatter Plot`, `Series Analysis`, `Autoencoder: Train` and the workflow `FLIM Data Augmentation Tuning` need two. Some also need a grouping column, for example `FLIRR Plot`. Until enough are selected, `Features` (or `Grouping`) is marked with an error. `Summarize` needs at least one statistic.

## Hidden settings

A field that allows only one value with the current settings is hidden. It appears again when other settings allow more values. For example, the plot dialogs show `Single figure` only for some numbers of grouping columns.

## Last settings used

When you click `OK`, the GUI keeps the settings of the dialog. The next time you open the same tool, its dialog opens with these settings, including the result prefix and the folder under `Save results`. Columns you selected that the table doesn't have are ignored. A feature with a close match in the table is replaced by it, and a note under the list shows the replacement, for example `Guessed: FAD a1% → FAD a1[%]`. The `Calculate` dialog always opens with an empty table of calculations (see [Calculate](/userguide/analysis/calculate.md)). `Cancel` keeps the settings that were there before.

The GUI also saves these settings to the user settings file, so they apply again the next time it starts (see [The user settings file](/userguide/settings.md#the-user-settings-file)). To keep them in a file of your own, use `File` > `Export Settings...` or `Save Settings...`.

## Result windows

Each table and plot that a tool makes opens in its own window. The window title is the type of the result and its name, for example `Table: Summary`, or `Plot: <name>` for a plot. If a window with that title is already open, a number is added, for example `Table: Summary-1`. The [`Window` menu](/userguide/appmenu.md#window) lists all windows.

The workflows made in code, such as `Basic FLIRR Analysis`, don't open windows for their results. Their results are saved in the results folder (see [Workflows](/userguide/workflows)). A workflow file opens a window for each result of its last steps (see [Results of a workflow file](/userguide/workflows.md#results-of-a-workflow-file)).

While a tool runs, a progress dialog shows its tasks (see [The progress dialog](/userguide/workflows.md#the-progress-dialog)).
