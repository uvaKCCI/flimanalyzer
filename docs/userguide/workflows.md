# Workflows

A workflow runs several tools in one run, for example to make summaries, relative changes and plots of the same features. Each tool is a step of the workflow. The workflow's dialog has the settings that the steps share, such as the grouping and the features, and passes them on to the steps. The controls that all dialogs have are described in [Tool dialogs](/userguide/dialogs).

Steps that don't depend on each other run concurrently, without waiting for each other. A [progress dialog](#the-progress-dialog) lists the steps while they run, and `Cancel` stops the workflow. When a workflow defined in code finishes, a window `<workflow name> Graph`, for example `Basic FLIRR Analysis Graph`, shows the steps in blue and the data and results passed between them in red. Failed steps have a dark red outline, and skipped steps are faded. A [workflow file](#workflow-files) opens no graph window. Then the [run summary](#the-run-summary) says how the run ended.

## Results

Workflows always save their results; `Save results` is always checked in their dialogs. The workflows defined in code, such as `Basic FLIRR Analysis`, open no windows for their results. A workflow file saves only the results of the steps with `save` in their `output`, and opens windows for the results of its last steps (see [Results of a workflow file](#results-of-a-workflow-file)).

In the GUI, each run gets its own folder: `<folder>/<workflow name>/<date and time>/`, where `<folder>` is the folder chosen under `Save results`. For example: `results/Basic FLIRR Analysis/2026-11-03_14-05-31/`. Steps that are run several times with different settings, for example the training of each model in the autoencoder workflows, save their results in subfolders of this folder, named after these settings. The other steps save their results directly in the folder. The files are saved as described in [Saving results](/userguide/dialogs.md#saving-results). `flimbatch` saves its results in other folders (see [Results](/userguide/batch.md#results)).

The folder also gets a file `run_summary.txt`. It lists when the workflow ran, the settings files used (the user settings file and the app settings file, with the settings converted or not used when it was read), and, for each step, its status, the resources it used (for example GPU or CPU) and its message. A completed step has a message only if its tool reported a warning (see [The run summary](#the-run-summary)).

## Validating the settings

Before the workflow runs, the dialog validates its settings against the selected data. A workflow may need a column that is not in the data, for example `FAD a1%` when the data has `FAD a1[%]`. In the dialog of a workflow defined in code, the `Strict` check box next to `Load Settings...` and `Save Settings...` (`Processing`) sets what happens; a workflow file sets it in its `processing` section (see [Workflow files](#workflow-files)):

* `Strict` on (the default): the field is marked with an error sign, and the workflow can't run until you choose a column.
* `Strict` off: the dialog uses the closest matching column of the same role and marks the field with a warning sign. Hover the mouse over the sign to see which column is used. The run summary lists these columns under "Notes". If no column is a close match, the field is marked with an error sign.

`Save Settings...` writes the setting into the tool file, as `"processing": {"strict": false}`. In a tool file, you can also set it per field, and let a workflow skip missing features or grouping columns, as in a workflow file's steps (see `processing` under [Workflow files](#workflow-files)). `flimbatch --run FILE` uses the setting of the tool file it runs (see [Batch Mode](/userguide/batch)).

## The progress dialog

While a tool or a workflow runs, a progress dialog shows:

* what is running, for example `Running: Summarize`, or what it is waiting for,
* a progress bar and the number of completed tasks, for example `3 of 12 tasks completed`,
* `Flow run on the Prefect server:` with a link to the run in the Prefect UI, if a Prefect server is used (see [Prefect server](/install/index.md#prefect-server)),
* `Results are saved in:` with the results folder, if the results are saved. Click it to open the folder in the file browser.
* `Tasks`: click it to see the list of all tasks and the status of each one (pending, running, completed, failed, cancelled or skipped).

![](/images/analysis/workflow-progress.png)

`Cancel` stops the run. Tasks that are running finish first, and the dialog says `Cancelling, waiting for ... to finish...`. Tasks that have not started yet don't run. The results of the completed tasks are kept in the results folder.

## The run summary

After every workflow, and after a tool run that was cancelled, a dialog says how the run ended:

* all tasks completed,
* how many tasks completed and which ones failed (the log file has the details; see [Log files](/install/index.md#log-files)),
* or after how many tasks the run was cancelled.

If tools reported warnings, the dialog lists them under `Warnings:`, each with the name of its task, up to five. A task with a warning is still completed, and its results are passed on to the next steps. The warnings are also in the log file and in `run_summary.txt`.

It also links to the results folder and to the flow run on the Prefect server, if there is one.

The results folder of the run has the file `run_summary.txt`. It lists each task with its step id (`Step`), its results folder in the run (`Folder`, for example `01-Summarize/a.txt`, the step's folder and the table's), its state, the resources it used and its message, for example a column it guessed.

![](/images/analysis/workflow-summary.png)

After a tool run that was not cancelled, there is no run summary. If the tool reported a warning, for example `Concatenate` when the rows of tables side by side don't match (see [Concatenate](/userguide/data/concat)), a message `<tool name>: warning` shows it after the result windows open. If a tool's tasks fail, a message lists the failed tasks.

## Workflow files

A workflow file defines a workflow as data: a JSON file that lists its steps, each a tool with its own settings. It works on tables: the tables read from data files ([Import Tables](/userguide/data/load.md#import-tables), or `flimbatch --run FILE`, see [Batch Mode](/userguide/batch)), or tables that are open. How the files are read is not part of the workflow file: these are the read settings of Import Tables, or of Open Tables in batch mode. The file and the read settings decide what a run does, so the same file, settings and data always give the same results, on any computer.

```
{
  "schema_version": 1,
  "name": "calc and aggregate",
  "description": "Calculates the FLIM features, joins the tables and summarizes the features.",
  "category": ["Workflow", "Summaries"],
  "output": {"formats": [{"kind": "table", "format": "csv"}]},
  "steps": [
    {"id": "1", "tool": "Calculate", "processing": {"skippable": {"calculations": "some"}}, "config": { ... }},
    {"id": "2", "tool": "Concatenate", "config": {"add_input": false}},
    {"id": "3", "tool": "Summarize", "inputs": ["2.1"], "description": "A summary per feature",
     "config": { ... }, "output": {"save": true}}
  ]
}
```

To start a workflow file from an example, `flimsettings workflow --show Import` prints the built-in workflow file, and `flimsettings tool --show NAME` prints the default settings of a tool, for the `config` of a step (see [flimsettings](/userguide/flimsettings)).

* `schema_version`: the version of the file format, `1`. A file with a higher version is refused, and the message says to upgrade FLIMAnalyzer.
* `name`: the workflow's name. Workflow files are found by it, like tools: `flimbatch --run "calc and aggregate"`. It must differ from every tool's and workflow's name (case is ignored); a file whose name is taken is not loaded, and the log says why.
* `description` (optional): what the workflow does. It is shown with the steps before a run, and as the text at the top of its dialog.
* `category` (optional): where the GUI shows the workflow.
    * The name of a menu, for example `"Analysis"`, or a list of a menu and its submenus, for example `["Workflow", "Summaries"]` for the submenu `Summaries` of the `Workflow` menu. The names are used as they are written: upper and lower case must agree with the menu's name, and a name that is not a menu adds a menu with that name. Without a submenu, the workflow is listed in the menu below the tools.
    * Without `category`, or with `null`: the `Workflow` menu.
    * `[]`: no menu. The workflow then runs only by its name, for example with `flimbatch --run`.
    * `File` > `Import Tables...` lists the workflow files with the category `["File", "Import"]` (see [Import Tables](/userguide/data/load.md#import-tables)). They are also in the submenu `File` > `Import`.
    * When the workflow is a favorite, its icon is in the tool panel group of its menu (see [Menus](/userguide/appmenu)).
* `output` (optional): `formats`, the formats in which the steps save their results, per kind of result: one entry per format, with its `kind` and `format` and, for plots, other options such as `dpi`. For example `[{"kind": "table", "format": "csv"}, {"kind": "plot", "format": "svg"}]`. A kind that no step makes is an error. See [Formats](#formats) for the steps' own formats.
* `processing` (optional): how the steps treat data that doesn't match their settings. It applies to every step (see `processing` of a step below).
* `steps`: one or more steps, each with:
    * `id`: a whole number from 1, for example `"3"` (the number `3` is read as `"3"`). Each step has its own id, and the id never changes. The id names the step's results folder, `<id>-<tool>`, with at least two digits, for example `03-Summarize`.
    * `tool`: the tool's name, as in the menus. A step can't be a workflow.
    * `inputs` (optional): which tables the step gets: `"4.1"` is output 1 of step 4 (`"4"` the same), `"input"` the tables the run starts from. Without `inputs`, a step gets output 1 of the step before it; the first step gets the run's tables. A step may only use the outputs of steps listed before it. The outputs of a step are numbered from 1 in the order its tool makes them. A tool that takes several tables, such as `Concatenate`, gets one input: the tables.
    * `description` (optional): a note for readers. FLIMAnalyzer doesn't use it.
    * `config`: the tool's settings, as in the `config` section of a tool file (`Save Settings...` in the tool's dialog writes a tool file); `{}` uses the tool's defaults. `classname` can be left out; the `classname` of another tool is an error.
    * `output` (optional): what the step saves.
        * `save` (default `false`): `true` saves all outputs of the step. A list such as `["3.1"]` saves only the outputs listed; they must be outputs of this step.
        * `formats` (optional): the formats of the step's results, per kind, as in the workflow's `output.formats`. A kind that the step's tool doesn't make is an error.
    * `processing` (optional): how the step treats data that doesn't match its settings. The workflow's `processing` applies to every step; a step's own fields take precedence, field by field.
        * `strict`: `true` (the default): a column that the settings name and the data doesn't have is an error. `false`: it is replaced by the closest column of the same role, and the run summary lists the replacement. One value for all fields, or one value per field, for example `{"features": false}`.
        * `skippable`: per field, which of its entries the step may skip if they don't apply to the data: `"none"` (the default): no entry, or the step fails. `"some"`: entries may be skipped if at least one applies; a field without entries has none to skip, and the step does not fail for it. `"all"`: all entries may be skipped, and the table passes on unchanged. Only some fields have entries that can be skipped: `grouping` and `features`, Rename Columns' `replacements`, Drop Columns' `drop`, Calculate's `calculations` and Filter's `features`, `categories` and `other` (the filters of each part). For example `{"calculations": "some"}`. The run summary lists what each step skipped.
        * `required`: per field, the entries that must apply although the field is skippable, for example `{"calculations": [{"name": "FLIRR"}]}` (a calculation by its name) or `{"features": ["FLIRR"]}`. Each entry must be in the step's settings.

### Formats

For each kind of result that a step makes, the formats are those of the first of these that lists the kind:

1. `--override output.formats=...` of `flimbatch` (see [Options](/userguide/batch.md#options)).
2. The step's `output.formats`.
3. The workflow's `output.formats`. In the GUI, the formats chosen in the workflow's dialog are used in its place.
4. The kind's default format: tables as tab-separated `.txt` files, plots as `.png` files at 300 dpi.

### Saving

Only the steps with `save` save their results. `flimbatch` doesn't run a workflow file in which no step saves, because the run would keep only its run summary; `--override output.save=true` makes every step save. A step that doesn't save, and whose outputs no later step uses, gets a warning before the run: its results are not kept. In the GUI, the results of these steps open in windows (see [Results of a workflow file](#results-of-a-workflow-file)).

### How the steps run

A run starts from its tables, for example the tables read from the files, one per file. Each step runs once per table, in parallel, until a step that takes several tables, such as `Concatenate`, joins them into one; the steps after it run once. Without such a step, every table runs through all steps on its own. A step can't combine tables per file with a joined table; `Merge` gets two single tables.

Some steps make their results in parts, one per feature: for example `Summarize` without `Single table` (`"single_table": false`) makes a table per feature, and a plot without `Single figure` makes a figure per feature. Such a step passes the parts on, and the steps after it run once per part. A step can't combine the parts of different steps.

Before a run, the file is validated: the ids, that every step only uses earlier steps' outputs, that every tool exists and its settings are valid, that `save` and `formats` name outputs and kinds of the step's tool, and the rules of [Saving](#saving). Then every step is validated against the columns it gets. Columns that a step's settings name and the data doesn't have are errors, unless the step's `processing` allows guesses (`strict`) or skipped entries (`skippable`). `flimsettings workflow --validate FILE` does the validation that needs no data, and `flimsettings workflow --resolve FILE` prints the file with every setting of every step stated, as `flimbatch` runs it (see [flimsettings](/userguide/flimsettings)). `flimbatch --dry-run` also validates the steps against the first rows of the data files (see [Validating a run first](/userguide/batch.md#validating-a-run-first)).

### The built-in workflow file

`Import` renames and drops the channels' columns, joins the tables and calculates the FLIM features. It saves the joined table with the calculated features. This is what `File` > `Import...` of FLIMAnalyzer 0.6 did with the default filename parser (see [Upgrading](/userguide/upgrading)). Its category is `["File", "Import"]`: `File` > `Import Tables...` lists it, and it is in `File` > `Import`. To take categories from the file names in the same run, write a copy into your workflows folder, for example with `flimsettings workflow --show Import > my-import.json`. Give the copy another `name` and add a Separate Categories step with the patterns of a preset (see [Separate Categories](/userguide/data/separate.md#presets)).

### Where workflow files are found

FLIMAnalyzer finds the built-in workflow file, and the workflow files in the folders of the workflow search path. The search path is the first of these that is set:

1. The folders given with `-w` (`--workflow-path`), to `flimanalyzer`, `flimbatch` or `flimsettings`.
2. The folders in the environment variable `FLIM_WORKFLOW_PATH` (separated by `:`, or `;` on Windows).
3. The folders of `workflow_paths` in the user settings file. This setting is read only from the user settings file; in an app settings file, it is not used, and a message says so. `flimbatch` and `flimsettings` read no user settings file, so they don't use it.
4. The folder `workflows` in the platform's settings folder, next to `usersettings.json`.

The folders of the search path also hold tool files: `flimbatch --run FILE` finds a workflow file or a tool file by its file name in these folders, then among the built-in workflow files, and `Save Settings...` in a tool's dialog starts in the first folder of the search path.

## Running a workflow file in the GUI

There are three ways to run a workflow file in the GUI:

* `File` > `Import Tables...` reads data files and runs the workflow chosen under `Workflow` on their tables (see [Import Tables](/userguide/data/load.md#import-tables)). `None (open the tables)`, the default, runs no workflow. `Other Workflow File...` runs a workflow file you choose, also one that is not in the workflow search path.
* The workflow's own entry in the menus, in the menu and submenu its `category` names (see `category` above). Its dialog lists the open tables under `Tables`: check the tables to run it on. `Save results` is checked and can't be unchecked. The folder and the formats start with the default results folder and the formats of the file's `output` section; the run saves in the folder and the formats you choose there. The dialog doesn't keep them for the next time.
* `Workflow` > `Run Workflow File...`: choose a workflow file. It runs on the table of the current window, with the rows that window shows. FLIMAnalyzer first shows the workflow's description and steps; click `Run`. The results are saved in the default results folder, in the formats of the file's `output` section.

Before the run, every step is validated against the columns of the tables. If a step names a column that the tables don't have, the run doesn't start, and a message lists the problems. If the run would open more windows than the app setting `max_windows` allows (see [Settings](/userguide/settings.md#layout-of-a-settings-file)), it doesn't start either; the message suggests running it with `flimbatch`, or adding a step that joins the tables, for example `Concatenate`.

## Results of a workflow file

A workflow file's run saves its results in `<folder>/<workflow name>/<date and time>/`, where `<folder>` is the folder chosen under `Save results`. Each step that saves has a folder of its own there, `<id>-<tool>`, for example `04-Calculate`. Below it, the results of a step that runs once per table are in a folder per table, and the results of a step that runs once per part in a folder per part. Only the results of the steps with `save` are saved, in the formats described in [Formats](#formats). A workflow defined in code, for example `Basic FLIRR Analysis`, saves the same way, in `<folder>/<workflow name>/<date and time>/`: each of its steps has a fixed id and a folder `<id>-<tool>`, and a step it runs in a loop, for example a plot per feature, has a folder per part.

When the run ends, a window opens for each result that no later step uses, for example the joined table of `Import`. Results that a step saved open as saved. The run summary shows how the run ended and where the results are. A workflow file opens no graph window.

## Basic FLIRR Analysis

**Menu Access:** `Workflow` > `Basic FLIRR Analysis`

**Tool panel icon:** ![](/images/workflow/flirrworkflow.png)

Makes summaries and relative changes of the features, and KDE, line, pair and scatter plots.

Settings:

* `Grouping`: the category columns to group the data by, in this order. Default: `Treatment`, `FOV`, `Cell`. The first column (for example `Treatment`) is the one the results compare.
* `Reference value`: the value of the first grouping column that the relative changes refer to, for example `ctrl`. Empty (default): the first value of that column, in the order of its categories (see [Order Category Values](/userguide/data/order)).
* `Scatter x (FAD a1 %)` and `Scatter y (NAD(P)H a2 %)`: the columns of the scatter plot. Empty (default): found by their names (FAD, a1 and % for x; NAD, a2 and % for y). Without them, there is no scatter plot.
* `Features`: the features to analyze. By default, the FAD and NAD(P)H amplitudes (a1, a2, a1%, a2%), lifetimes (t1, t2) and photons.
* `Strict` (next to the settings buttons): see [Validating the settings](#validating-the-settings).

The workflow uses the grouping in these steps:

* `Stats-Table: Summary`: count, median, mean, standard deviation and standard error of the mean of each feature, for each value of the first grouping column.
* `Counts-Table: Summary`: the number of values of the first feature for each combination of all grouping columns.
* Pair plots of the FAD features (`FAD-`) and of the NAD(P)H features (`NADPH-`), coloured by the first grouping column.
* Relative changes (see [Relative Change](/userguide/analysis/relchange)): the features are divided by their **mean** in the rows with the reference value of the first grouping column. The rows are matched by the other grouping columns, for example each `FOV` and `Cell`. The new features are named `rel <feature>`.
* `Relative Stats-Table: Summary`: the mean of each relative change, for each combination of all grouping columns.
* A line plot of each relative change, along the first grouping column, with a line for each value of the second grouping column.
* A KDE plot of each feature and a scatter plot, with a colour for each value of the first grouping column.

Example:
![](/images/analysis/workflow-results.png)

## FLIM Data Augmentation Tuning

**Menu Access:** `Workflow` > `FLIM Data Augmentation Tuning`

**Tool panel icon:** ![](/images/workflow/aetuneworkflow.png)

Trains an autoencoder for each combination of batch size, learning rate and weight decay, then augments the data with each model. The results include plots of the training and validation loss, which show how the training went. Correlation heatmaps and KDE plots of the features, of the original and of each augmented data set, show how well the augmented data matches the original data.

Settings:

* `Grouping`: the training and validation sets are split by these groups. Default: `Treatment`, `FOV`, `Cell`.
* `Features`: the features the autoencoders use. By default, the FAD and NAD(P)H amplitudes (a1, a2), lifetimes (t1, t2) and photons.
* `Time series`: the category column with the time points. The KDE plots and the summaries of the augmented data are grouped by it. Default: `Treatment`.
* `Resources`: the device and threads of the training and augmentation (see [Resources](/userguide/dialogs.md#resources)).
* `Training`: the settings of [Autoencoder Train](/userguide/analysis/aetrain), without those the workflow sets. Defaults: 6 epochs, learning rates 1e-5 and 2e-5, weight decays 1e-7 and 1e-8, batch sizes 128 and 64 (8 models), `Rescale output to the data's units` on, a checkpoint every 2 epochs, and the architecture `AE Simulator 1-6`.
* `Augment`: the settings of [Autoencoder Augment Data](/userguide/analysis/aeaugment), without those the workflow sets. Defaults: 4 copies, `Add noise` off.
* `Strict` (next to the settings buttons): see [Validating the settings](#validating-the-settings).

## FLIM Feature Analysis

**Menu Access:** `Workflow` > `FLIM Feature Analysis`

**Tool panel icon:** ![](/images/workflow/aefeatureworkflow.png)

Uses two data tables, chosen under `Training data` and `Data`: training data (for example the augmented data from `FLIM Data Augmentation Tuning`) and the data to analyze. The workflow trains an autoencoder on the training data for each combination of batch size, learning rate and weight decay. It then runs each model, as it is after the last training round (epoch), on the data to analyze. Finally, it compares the first feature from each model with FLIRR and with the first principal component of a PCA. The comparison includes summaries, normalized changes along the time series, KS statistics and plots. Like PCA, the autoencoder reduces the features to a few values. Unlike PCA, it is not limited to weighted sums of the features.

Settings:

* `Grouping`, `Features`, `Time series` and `Resources`, and `Strict` next to the settings buttons: as in [FLIM Data Augmentation Tuning](#flim-data-augmentation-tuning).
* `Training`: the settings of [Autoencoder Train](/userguide/analysis/aetrain), without those the workflow sets. The defaults are those of FLIM Data Augmentation Tuning, except the architecture, `AE Dimensionality Reduction 2-10`.
* `Run`: the settings of [Autoencoder Run](/userguide/analysis/aerun), without those the workflow sets.
* `Control`: the value of the time series column used as control. Default: `Ctrl`. The tables of normalized changes are sorted by the changes from this time point to the next. Upper and lower case don't matter.
