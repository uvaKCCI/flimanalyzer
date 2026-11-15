# Workflows

A workflow runs several tools in one go, for example to make summaries, relative changes and plots of the same features. Each tool is a step of the workflow. The workflow's dialog has the settings that the steps share, such as the grouping and the features, and passes them on to the steps. The controls that all dialogs have are described in [Tool dialogs](/userguide/dialogs).

Steps that don't depend on each other run concurrently, without waiting for each other. A [progress dialog](#the-progress-dialog) lists the steps while they run, and `Cancel` stops the workflow. When a workflow made in code finishes, a window `<workflow name> Graph`, for example `Basic FLIRR Analysis Graph`, shows the steps in blue and the data and results passed between them in red. Failed steps have a dark red outline, and skipped steps are faded. A [workflow file](#workflow-files) opens no graph window. Then the [run summary](#the-run-summary) says how the run ended.

## Results

Workflows always save their results; `Save results` is always checked in their dialogs. The workflows made in code, such as `Basic FLIRR Analysis`, open no windows for their results. A workflow file saves only the results of the steps marked `save`, and opens windows for the results of its last steps (see [Results of a workflow file](#results-of-a-workflow-file)).

Each run gets its own folder: `<folder>/<workflow name>/<date and time>/`, where `<folder>` is the folder chosen under `Save results`. For example: `results/Basic FLIRR Analysis/2026-11-03_14-05-31/`. Steps that are run several times with different settings, for example the training of each model in the autoencoder workflows, save their results in subfolders of this folder, named after these settings. The other steps save their results directly in the folder. The files are saved as described in [Saving results](/userguide/dialogs.md#saving-results).

The folder also gets a file `run_summary.txt`. It lists when the workflow ran, the settings files used (the user settings file and the app settings file, with the settings converted or not used when it was read), and, for each step, its status, the resources it used (for example GPU or CPU) and its message. A completed step has a message only if its tool reported a warning (see [The run summary](#the-run-summary)).

## Validating the settings

Before the workflow runs, the dialog validates its settings against the selected data. A workflow may need a column that is not in the data, for example `FAD a1%` when the data has `FAD a1[%]`. The `Strict` check box next to `Load Settings...` and `Save Settings...` (`Processing`) sets what happens:

* `Strict` on (the default): the field is marked with an error sign, and the workflow can't run until you choose a column.
* `Strict` off: the dialog uses the closest matching column of the same kind and marks the field with a warning sign. Hover the mouse over the sign to see which column is used. The run summary lists these columns under "Notes". If no column is a close match, the field is marked with an error sign.

`Save Settings...` writes the setting into the tool file, as `"processing": {"strict": false}`. In a tool file, you can also set it per field, and let a workflow skip missing features or grouping columns, as in a workflow file's steps (see `processing` under [Workflow files](#workflow-files)). `flimbatch` uses the setting of the tool file it runs (see [Batch Mode](/userguide/batch)).

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

![](/images/analysis/workflow-summary.png)

After a tool run that was not cancelled, there is no run summary. If the tool reported a warning, for example `Concatenate` when the rows of tables side by side don't match (see [Concatenate](/userguide/data/concat)), a message `<tool name>: warning` shows it after the result windows open. If a tool's tasks fail, a message lists the failed tasks.

## Workflow files

A workflow file defines a workflow as data: a JSON file that lists its steps, each a tool with its own settings. It works on tables: the tables read from data files ([Import Tables](/userguide/data/load.md#import-tables), or `flimbatch --workflow FILE`, see [Batch Mode](/userguide/batch)), or tables that are open. How the files are read is not part of the workflow file: these are the read settings of Import Tables, or of Open Tables in batch mode. The file and the read settings decide what a run does, so the same file, settings and data always give the same results, on any computer.

```
{
  "schema_version": 1,
  "name": "calc and aggregate",
  "tags": ["summaries"],
  "autosave": {"formats": [{"kind": "table", "format": "csv"}]},
  "steps": [
    {"id": "1", "tool": "Calculate", "processing": {"skippable": {"calculations": "some"}}, "config": { ... }},
    {"id": "2", "tool": "Concatenate", "config": {"add_input": false}},
    {"id": "3", "tool": "Summarize", "config": { ... }, "save": true}
  ]
}
```

* `name`: the workflow's name. Workflow files are found by it, like tools: `flimbatch --run "calc and aggregate"`. It must differ from every tool's and workflow's name (case is ignored); a file whose name is taken is not loaded, and the log says why.
* `description` (optional): what the workflow does. It is shown with the steps before a run, and as the text at the top of its dialog.
* `tags` (optional): words that group the workflow, for example `["file", "import"]`.
    * `File` > `Import Tables...` lists the workflow files tagged `import` (see [Import Tables](/userguide/data/load.md#import-tables)).
    * A tag that names a menu (`file`, `data`, `analysis`, `plot` or `workflow`; case is ignored) puts the workflow in that menu, and its icon in that group of the tool panel when it is a favorite (see [Menus](/userguide/appmenu)). Without such a tag, it is in the `Workflow` menu and group.
    * In its menu, the workflow is in a submenu named after its first other tag (for example `Import`, or `Summaries` for `"summaries"`); without one, in the submenu `Workflow Files`. The built-in workflow file is in `Workflow` > `Import`.
* `autosave`: the formats the results are saved in (`formats`, as in the settings, see [Settings](/userguide/settings)).
* `steps`, each with:
    * `id`: an identifier that never changes, for example a number.
    * `tool`: the tool's name, as in the menus. A step can't be a workflow.
    * `inputs` (optional): which tables the step gets: `"4.1"` is output 1 of step 4 (`"4"` the same), `"input"` the tables the run starts from. Without `inputs`, a step gets output 1 of the step before it; the first step gets the run's tables. A step may only use the outputs of steps listed before it. The outputs of a step are numbered from 1 in the order its tool makes them.
    * `config`: the tool's settings: the `config` part of the tool's section in a settings file's `tools` section, without `autosave` (see [Settings](/userguide/settings)); `{}` uses the tool's defaults.
    * `outputs` (optional): names for the step's outputs, by number, for example `{"1": "Table: Summary"}`. FLIMAnalyzer reads them but doesn't use them.
    * `save` (default `false`): `true` saves the step's outputs, or a list such as `["3.1"]` saves some of them. Only these are saved.
    * `processing` (optional): how the step treats data that doesn't match its settings. A `processing` section at the top of the file applies to every step; a step's own fields take precedence, field by field.
        * `strict`: `true` (the default): a column that the settings name and the data doesn't have is an error. `false`: it is replaced by the closest column of the same role, and the run summary lists the replacement. One value for all fields, or one value per field, for example `{"features": false}`.
        * `skippable`: per field, which of its entries the step may skip if they don't apply to the data: `"none"` (the default): no entry, or the step fails. `"some"`: entries may be skipped if at least one applies. `"all"`: all entries may be skipped, and the table passes on unchanged. Only some fields have entries that can be skipped: `grouping` and `features`, Rename Columns' `replacements`, Drop Columns' `drop`, Calculate's `calculations` and Filter's `filters`. For example `{"calculations": "some"}`. The run summary lists what each step skipped.
        * `required`: per field, the entries that must apply although the field is skippable, for example `{"calculations": [{"name": "FLIRR"}]}` (a calculation by its name) or `{"features": ["FLIRR"]}`. Each entry must be in the step's settings.

A run starts from its tables, for example the tables read from the files, one per file. Each step runs once per table, in parallel, until a step that takes several tables, such as `Concatenate`, joins them into one; the steps after it run once. Without such a step, every table runs through all steps on its own. A step can't combine tables per file with a joined table; `Merge` gets two single tables.

Before a run, the file is validated: the ids, that every step only uses earlier steps' outputs, that every tool exists and its settings are valid. Columns that a step's settings name and the data doesn't have are errors, unless the step's `processing` allows guesses (`strict`) or skipped entries (`skippable`).

**The built-in workflow file.** `Import` processes the tables as `File` > `Import...` did up to FLIMAnalyzer 0.6 with the default filename parser: it renames and drops the channels' columns, joins the tables and calculates the FLIM features. It is tagged `import`: `File` > `Import Tables...` lists it, and it is in `Workflow` > `Import`. To take categories from the file names in the same run, copy it from FLIMAnalyzer's folder `flim/workflow/files` into your workflows folder, give it another `name` and add a Separate Categories step with the patterns of a preset (see [Separate Categories](/userguide/data/separate.md#presets)).

**Where workflow files are found:** the built-in one, and the files in the folders of the workflow search path. This is, in this order:

1. The folders in the environment variable `FLIM_WORKFLOW_PATH`, if it is set (separated by `:`, or `;` on Windows). They replace the other folders.
2. Otherwise, the folders of `workflow_paths` in the settings: in the GUI, from the user settings file or the app settings file; in `flimbatch`, which reads no user settings file, only from the `-s` file.
3. Otherwise, the folder `workflows` in the platform's settings folder, next to `usersettings.json`.

`--workflow` takes a path, or the name of a file in these folders.

## Running a workflow file in the GUI

There are three ways to run a workflow file in the GUI:

* `File` > `Import Tables...` reads data files and runs the workflow chosen under `Workflow` on their tables (see [Import Tables](/userguide/data/load.md#import-tables)). `None (open the tables)`, the default, runs no workflow. `Other Workflow File...` runs a workflow file you choose, also one that is not in the workflow search path.
* The workflow's own entry in the menus, in the submenu its tags name (see `tags` above). Its dialog lists the open tables under `Tables`: check the tables to run it on. `Save results` is checked and can't be unchecked. The folder and the formats start with the default results folder and the formats of the file's `autosave` section; the run saves in the folder and the formats you choose there. The dialog doesn't keep them for the next time.
* `Workflow` > `Run Workflow File...`: choose a workflow file. It runs on the table of the current window, with the rows that window shows. FLIMAnalyzer first shows the workflow's description and steps; click `Run`. The results are saved in the default results folder, in the formats of the file's `autosave` section.

Before the run, every step is validated against the columns of the tables. If a step names a column that the tables don't have, the run doesn't start, and a message lists the problems. If the run would open more windows than the app setting `max_windows` allows (see [Settings](/userguide/settings.md#layout-of-a-settings-file)), it doesn't start either; the message suggests running it with `flimbatch`, or adding a step that joins the tables, for example `Concatenate`.

## Results of a workflow file

A workflow file's run saves its results in `<folder>/<workflow name>/<date and time>/`, where `<folder>` is the folder chosen under `Save results`. Only the results of the steps marked `save` are saved, in the formats of the file's `autosave` section or those chosen in its dialog.

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
* `Training`: the settings of [Autoencoder: Train](/userguide/analysis/aetrain), without those the workflow sets. Defaults: 6 epochs, learning rates 1e-5 and 2e-5, weight decays 1e-7 and 1e-8, batch sizes 128 and 64 (8 models), `Rescale output to the data's units` on, a checkpoint every 2 epochs, and the architecture `AE Simulator 1-6`.
* `Augment`: the settings of [Autoencoder: Augment Data](/userguide/analysis/aeaugment), without those the workflow sets. Defaults: 4 copies, `Add noise` off.
* `Strict` (next to the settings buttons): see [Validating the settings](#validating-the-settings).

## FLIM Feature Analysis

**Menu Access:** `Workflow` > `FLIM Feature Analysis`

**Tool panel icon:** ![](/images/workflow/aefeatureworkflow.png)

Uses two data tables, chosen under `Training data` and `Data`: training data (for example the augmented data from `FLIM Data Augmentation Tuning`) and the data to analyze. The workflow trains an autoencoder on the training data for each combination of batch size, learning rate and weight decay. It then runs each model, as it is after the last training round (epoch), on the data to analyze. Finally, it compares the first feature from each model with FLIRR and with the first principal component of a PCA. The comparison includes summaries, normalized changes along the time series, KS statistics and plots. Like PCA, the autoencoder reduces the features to a few values. Unlike PCA, it is not limited to weighted sums of the features.

Settings:

* `Grouping`, `Features`, `Time series` and `Resources`, and `Strict` next to the settings buttons: as in [FLIM Data Augmentation Tuning](#flim-data-augmentation-tuning).
* `Training`: the settings of [Autoencoder: Train](/userguide/analysis/aetrain), without those the workflow sets. The defaults are those of FLIM Data Augmentation Tuning, except the architecture, `AE Dimensionality Reduction 2-10`.
* `Run`: the settings of [Autoencoder: Run](/userguide/analysis/aerun), without those the workflow sets.
* `Control`: the value of the time series column used as control. Default: `Ctrl`. The tables of normalized changes are sorted by the changes from this time point to the next. Upper and lower case don't matter.
