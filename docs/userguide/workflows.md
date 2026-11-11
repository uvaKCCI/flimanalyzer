# Workflows

A workflow runs several tools in one go, for example to make summaries, relative changes and plots of the same features. Each tool is a step of the workflow. The workflow's dialog has the settings that the steps share, such as the grouping and the features, and passes them on to the steps. The controls that all dialogs have are described in [Tool dialogs](/userguide/dialogs).

Steps that don't depend on each other run concurrently, without waiting for each other. A [progress dialog](#the-progress-dialog) lists the steps while they run, and `Cancel` stops the workflow. When the workflow finishes, a window `<workflow name> Graph`, for example `Basic FLIRR Analysis Graph`, shows the steps in blue and the data and results passed between them in red. Failed steps have a dark red outline, and skipped steps are faded. Then the [run summary](#the-run-summary) says how the run ended.

## Results

Workflows always save their results; `Save results` is always checked in their dialogs. The results are not opened in windows.

Each run gets its own folder: `<folder>/<workflow name>/<date and time>/`, where `<folder>` is the folder chosen under `Save results`. For example: `results/Basic FLIRR Analysis/2026-11-03_14-05-31/`. Steps that are run several times with different settings, for example the training of each model in the autoencoder workflows, save their results in subfolders of this folder, named after these settings. The other steps save their results directly in the folder. The files are saved as described in [Saving results](/userguide/dialogs.md#saving-results).

The folder also gets a file `run_summary.txt`. It lists when the workflow ran, the settings files used (the user settings file and the app settings file, with the settings converted or not used when it was read), and, for each step, its status, the resources it used (for example GPU or CPU) and its message. A completed step has a message only if its tool reported a warning (see [The run summary](#the-run-summary)).

## Checking the settings

Before the workflow runs, the dialog checks its settings against the selected data. A workflow may need a column that is not in the data, for example `FAD a1%` when the data has `FAD a1[%]`. The dialog then uses the closest matching column and marks the field with a warning sign. Hover the mouse over the sign to see which column is used. The run summary lists these columns under "Notes". If no column is a close match, the field is marked with an error sign, and the workflow can't run until you choose a column.

The `Strict` setting of each workflow sets whether a missing column is guessed or is an error:

* `Automatic` (default): follows the option `--strict` or `--no-strict` (see [Command-line options](/install/index.md#command-line-options)). Without it, missing columns are guessed in the GUI, and are an error in [batch mode](/userguide/batch).
* `Yes`: always an error, also in the GUI. Choose the column yourself.
* `No`: always guessed, also in batch mode.

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
    {"id": "1", "tool": "Calculate", "processing": "allow_partial", "config": { ... }},
    {"id": "2", "tool": "Concatenate", "config": {"add_input": false}},
    {"id": "3", "tool": "Summarize", "config": { ... }, "save": true}
  ]
}
```

* `name`: the workflow's name. Workflow files are found by it, like tools: `flimbatch --run "calc and aggregate"`. It must differ from every tool's and workflow's name (case is ignored); a file whose name is taken is not loaded, and the log says why.
* `tags` (optional): words that group the workflow, for example `["file", "import"]`.
    * `File` > `Import Tables...` lists the workflow files tagged `import` (see [Import Tables](/userguide/data/load.md#import-tables)).
    * A tag that names a menu (`file`, `data`, `analysis`, `plot` or `workflow`; case is ignored) puts the workflow in that menu, and its icon in that group of the tool panel when it is a favorite (see [Menus](/userguide/appmenu)). Without such a tag, it is in the `Workflow` menu and group.
    * In its menu, the workflow is in a submenu named after its first other tag (for example `Import`, or `Summaries` for `"summaries"`); without one, in the submenu `Workflow Files`. The built-in ones are in `Workflow` > `Import`.
* `autosave`: the formats the results are saved in (`formats`, as in the settings, see [Settings](/userguide/settings)).
* `steps`, each with:
    * `id`: an identifier that never changes, for example a number.
    * `tool`: the tool's name, as in the menus.
    * `inputs` (optional): which tables the step gets: `"4.1"` is output 1 of step 4 (`"4"` the same), `"input"` the tables the run starts from. Without `inputs`, a step gets output 1 of the step before it; the first step gets the run's tables. A step may only use the outputs of steps listed before it. The outputs of a step are numbered from 1 in the order its tool makes them.
    * `config`: the tool's settings, as in a settings file's `tools` section (see [Settings](/userguide/settings)); `{}` uses the tool's defaults.
    * `save` (default `false`): `true` saves the step's outputs, or a list such as `["3.1"]` saves some of them. Only these are saved.
    * `processing`: how much of its settings a step must apply to the data. `require_all` (the default): every part, or the step fails. `allow_partial`: what applies is done and the rest is skipped with a warning, but at least one part must apply. `allow_none`: the step may apply nothing, and the table passes on unchanged. Parts are, for example, Rename Columns' replacements, Drop Columns' rules, Calculate's calculations and Filter's filters. The run summary lists what each step skipped.

A run starts from its tables, for example the tables read from the files, one per file. Each step runs once per table, in parallel, until a step that takes several tables, such as `Concatenate`, joins them into one; the steps after it run once. Without such a step, every table runs through all steps on its own. A step can't combine tables per file with a joined table; `Merge` gets two single tables.

Before a run, the file is checked: the ids, that every step only uses earlier steps' outputs, that every tool exists and its settings are valid. Columns that a step's settings name and the data doesn't have are always errors in workflow files; they are not replaced by the closest match.

**The built-in workflow file.** `Import` processes the tables as `File` > `Import...` did up to FLIMAnalyzer 0.6 with the default filename parser: it renames and drops the channels' columns, joins the tables and calculates the FLIM features. It is tagged `import`: `File` > `Import Tables...` lists it, and it is in `Workflow` > `Import`. To take categories from the file names in the same run, copy it from FLIMAnalyzer's folder `flim/workflow/files` into your workflows folder, give it another `name` and add a Separate Categories step with the patterns of a preset (see [Separate Categories](/userguide/data/separate.md#presets)).

**Where workflow files are found:** the built-in ones, and the files in the folders of `workflow_paths` in the user settings file (default: the folder `workflows` in the platform's settings folder, next to `usersettings.json`). The environment variable `FLIM_WORKFLOW_PATH` (folders separated by `:`, or `;` on Windows) takes precedence. `--workflow` takes a path, or the name of a file in these folders.

## Basic FLIRR Analysis

**Menu Access:** `Workflow` > `Basic FLIRR Analysis`

**Tool panel icon:** ![](/images/workflow/flirrworkflow.png)

Makes summaries and relative changes of the features, and KDE, line, pair and scatter plots.

Settings:

* `Grouping`: the category columns to group the data by, in this order. Default: `Treatment`, `FOV`, `Cell`. The first column (for example `Treatment`) is the one the results compare.
* `Reference value`: the value of the first grouping column that the relative changes refer to, for example `ctrl`. Empty (default): the first value of that column, in the order of its categories (see [Order Categories](/userguide/data/order)).
* `Scatter x (FAD a1 %)` and `Scatter y (NAD(P)H a2 %)`: the columns of the scatter plot. Empty (default): found by their names (FAD, a1 and % for x; NAD, a2 and % for y). Without them, there is no scatter plot.
* `Features`: the features to analyze. By default, the FAD and NAD(P)H amplitudes (a1, a2, a1%, a2%), lifetimes (t1, t2) and photons.
* `Strict`: see [Checking the settings](#checking-the-settings).

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
* `Strict`: see [Checking the settings](#checking-the-settings).

## FLIM Feature Analysis

**Menu Access:** `Workflow` > `FLIM Feature Analysis`

**Tool panel icon:** ![](/images/workflow/aefeatureworkflow.png)

Uses two data tables, chosen under `Training data` and `Data`: training data (for example the augmented data from `FLIM Data Augmentation Tuning`) and the data to analyze. The workflow trains an autoencoder on the training data for each combination of batch size, learning rate and weight decay. It then runs each model, as it is after the last training round (epoch), on the data to analyze. Finally, it compares the first feature from each model with FLIRR and with the first principal component of a PCA. The comparison includes summaries, normalized changes along the time series, KS statistics and plots. Like PCA, the autoencoder reduces the features to a few values. Unlike PCA, it is not limited to weighted sums of the features.

Settings:

* `Grouping`, `Features`, `Time series`, `Resources` and `Strict`: as in [FLIM Data Augmentation Tuning](#flim-data-augmentation-tuning).
* `Training`: the settings of [Autoencoder: Train](/userguide/analysis/aetrain), without those the workflow sets. The defaults are those of FLIM Data Augmentation Tuning, except the architecture, `AE Dimensionality Reduction 2-10`.
* `Run`: the settings of [Autoencoder: Run](/userguide/analysis/aerun), without those the workflow sets.
* `Control`: the value of the time series column used as control. Default: `Ctrl`. The tables of normalized changes are sorted by the changes from this time point to the next. Upper and lower case don't matter.
