# Workflows

A workflow runs several tools in one go, for example summaries, relative changes and plots of the same features. Its dialog has the settings that the steps share, such as the grouping and the features; the workflow passes them to its steps.

Steps that don't depend on each other run at the same time. A progress dialog lists the steps while they run, and `Cancel` stops the workflow. When it finishes, a graph shows the steps (blue) and the data and results they pass on (red); failed steps have a dark red outline, skipped steps are faded.

The results of a workflow are always saved, in the folder chosen in its dialog, together with `run_summary.txt`: when the workflow ran, and the status, resources (e.g. GPU or CPU) and message of each step.

## Checking the settings

The dialog checks the workflow's settings against the selected data before it runs. If a column that the workflow needs is not in the data, for example `FAD a1%` when the data has `FAD a1[%]`, the dialog uses the closest column and marks the field with a warning sign; hover over the marker to see which column is used. The run summary lists these columns under "Notes". A column without a close match is an error (error sign), and the workflow can't run until it is chosen.

In [batch mode](/userguide/batch), missing columns are errors unless `--allow-guesses` is given.

## Basic FLIRR Analysis

**Menu Access:** `Workflow` > `Basic FLIRR Analysis`

**Toolbar Icon:** ![](/images/workflow/flirrworkflow.png)

Summaries and relative changes of the features, grouped by the first grouping column, with KDE, line, pair and scatter plots.

Example:
![](/images/analysis/workflow-results.png)

## FLIM Data Augmentation Tuning

**Menu Access:** `Workflow` > `FLIM Data Augmentation Tuning`

**Toolbar Icon:** ![](/images/workflow/aetuneworkflow.png)

Trains an autoencoder for each combination of batch size, learning rate and weight decay, then augments the data with each model. The results include heatmaps and training loss plots to check how well the augmented data matches the original data.

## FLIM Feature Analysis

**Menu Access:** `Workflow` > `FLIM Feature Analysis`

**Toolbar Icon:** ![](/images/workflow/aefeatureworkflow.png)

Uses two data tables: training data (for example the augmented data from `FLIM Data Augmentation Tuning`) and the data to analyze. It trains an autoencoder for each combination of batch size, learning rate and weight decay on the training data, runs the models of the last epoch on the data, and compares their first feature with FLIRR and the first principal component: summaries, normalized changes along the time series, KS statistics and plots. Like PCA, the autoencoder reduces the features to a few values, but it is not limited to linear combinations.
