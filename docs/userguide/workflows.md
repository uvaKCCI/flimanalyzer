# Workflows

A workflow runs several tools in one go, for example to make summaries, relative changes and plots of the same features. Each tool is a step of the workflow. The workflow's dialog has the settings that the steps share, such as the grouping and the features, and passes them on to the steps. The controls that all dialogs have are described in [Tool dialogs](/userguide/dialogs).

Steps that don't depend on each other run concurrently, without waiting for each other. A [progress dialog](#the-progress-dialog) lists the steps while they run, and `Cancel` stops the workflow. When the workflow finishes, a window `<workflow name> Graph`, for example `Basic FLIRR Analysis Graph`, shows the steps in blue and the data and results passed between them in red. Failed steps have a dark red outline, and skipped steps are faded. Then the [run summary](#the-run-summary) says how the run ended.

## Results

Workflows always save their results; `Save results in` is always checked in their dialogs. The results are not opened in windows.

Each run gets its own folder: `<folder>/<workflow name>/<date and time>/`, where `<folder>` is the folder chosen under `Save results in`. For example: `FLIMAnalyzerResults/Basic FLIRR Analysis/2026-11-03_14-05-31/`. Steps that are run several times with different settings, for example the training of each model in the autoencoder workflows, save their results in subfolders of this folder, named after these settings. The other steps save their results directly in the folder. The files are saved as described in [Saving results](/userguide/dialogs.md#saving-results).

The folder also gets a file `run_summary.txt`. It lists when the workflow ran and, for each step, its status, the resources it used (for example GPU or CPU) and its message.

## Checking the settings

Before the workflow runs, the dialog checks its settings against the selected data. A workflow may need a column that is not in the data, for example `FAD a1%` when the data has `FAD a1[%]`. The dialog then uses the closest matching column and marks the field with a warning sign. Hover the mouse over the sign to see which column is used. The run summary lists these columns under "Notes". If no column is a close match, the field is marked with an error sign, and the workflow can't run until you choose a column.

The `Strict` setting of each workflow sets whether a missing column is guessed or is an error:

* `Automatic` (default): guessed in the GUI. In [batch mode](/userguide/batch), it is an error unless `--allow-guesses` is given.
* `Yes`: always an error, also in the GUI. Choose the column yourself.
* `No`: always guessed, also in batch mode.

## The progress dialog

While a tool or a workflow runs, a progress dialog shows:

* what is running, for example `Running: Summarize`, or what it is waiting for,
* a progress bar and the number of completed tasks, for example `3 of 12 tasks completed`,
* `Flow run on the Prefect server:` with a link to the run in the Prefect UI, if a Prefect server is used (see [Prefect server](/install/index.md#prefect-server)),
* `Results are saved in:` with the results folder, if the results are saved. Click it to open the folder in the file browser.
* `Tasks`: click it to see the list of all tasks and the status of each one (pending, running, completed, failed, cancelled or skipped).

`Cancel` stops the run. Tasks that are running finish first, and the dialog says `Cancelling, waiting for ... to finish...`. Tasks that have not started yet don't run. The results of the completed tasks are kept in the results folder.

## The run summary

After every workflow, and after a tool run that was cancelled, a dialog says how the run ended:

* all tasks completed,
* how many tasks completed and which ones failed (the log file `flimanalyzer.log` has the details; see [Command-line options](/install/index.md#command-line-options)),
* or after how many tasks the run was cancelled.

It also links to the results folder and to the flow run on the Prefect server, if there is one.

If a tool's tasks fail, a message lists the failed tasks.

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
* `Time series`: the category column with the time points. Default: `Treatment`.
* `Resources`: the device and threads of the training and augmentation (see [Resources](/userguide/dialogs.md#resources)).
* `Training`: the settings of [Autoencoder: Train](/userguide/analysis/aetrain), without those the workflow sets. Defaults: 6 epochs, learning rates 1e-5 and 2e-5, weight decays 1e-7 and 1e-8, batch sizes 128 and 64 (8 models), `Rescale` on, a checkpoint every 2 epochs, and the architecture `AE Simulator 1-6`.
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
