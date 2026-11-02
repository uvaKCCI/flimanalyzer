# Workflows

A workflow runs several tools in one go, for example to make summaries, relative changes and plots of the same features. Each tool is a step of the workflow. The workflow's dialog has the settings that the steps share, such as the grouping and the features, and passes them on to the steps.

Steps that don't depend on each other run at the same time. A progress dialog lists the steps while they run, and `Cancel` stops the workflow. When the workflow finishes, a diagram shows the steps in blue and the data and results passed between them in red. Failed steps have a dark red outline, and skipped steps are faded.

The results of a workflow are always saved in the folder chosen in its dialog. The folder also gets a file `run_summary.txt`. It lists when the workflow ran and, for each step, its status, the resources it used (for example GPU or CPU) and its message.

## Checking the settings

Before the workflow runs, the dialog checks its settings against the selected data. A workflow may need a column that is not in the data, for example `FAD a1%` when the data has `FAD a1[%]`. The dialog then uses the closest matching column and marks the field with a warning sign. Hover the mouse over the sign to see which column is used. The run summary lists these columns under "Notes". If no column is a close match, the field is marked with an error sign, and the workflow can't run until you choose a column.

In [batch mode](/userguide/batch), missing columns are errors unless `--allow-guesses` is given.

## Basic FLIRR Analysis

**Menu Access:** `Workflow` > `Basic FLIRR Analysis`

**Toolbar Icon:** ![](/images/workflow/flirrworkflow.png)

Makes summaries and relative changes of the features, grouped by the first grouping column, and KDE, line, pair and scatter plots.

Example:
![](/images/analysis/workflow-results.png)

## FLIM Data Augmentation Tuning

**Menu Access:** `Workflow` > `FLIM Data Augmentation Tuning`

**Toolbar Icon:** ![](/images/workflow/aetuneworkflow.png)

Trains an autoencoder for each combination of batch size, learning rate and weight decay, then augments the data with each model. The results include plots of the training and validation loss, which show how the training went. Correlation heatmaps and KDE plots of the features, of the original and of each augmented data set, show how well the augmented data matches the original data.

## FLIM Feature Analysis

**Menu Access:** `Workflow` > `FLIM Feature Analysis`

**Toolbar Icon:** ![](/images/workflow/aefeatureworkflow.png)

Uses two data tables: training data (for example the augmented data from `FLIM Data Augmentation Tuning`) and the data to analyze. The workflow trains an autoencoder on the training data for each combination of batch size, learning rate and weight decay. It then runs each model, as it is after the last training round (epoch), on the data to analyze. Finally, it compares the first feature from each model with FLIRR and with the first principal component of a PCA. The comparison includes summaries, normalized changes along the time series, KS statistics and plots. Like PCA, the autoencoder reduces the features to a few values. Unlike PCA, it is not limited to weighted sums of the features.
