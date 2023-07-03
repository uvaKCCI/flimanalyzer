# Workflows
The workflow tools allows the user to save and run several analysis steps, making it more efficient to run analysis on multiple datasets. Say, for example, you need to filter the data, run the `PCA` tool, and plot the first two principal components on a scatter plot for many sets of experimental data. Manually configuring the settings and performing this analysis is time consuming, but with the workflow tools, you can save and run these analysis steps. Saving a workflow requires the user to edit the basicflow.py, aetune.py, and aefeature.py files, as the current workflows are configured to the needs of the Keck Center.

Example Workflow:
![](/images/analysis/workflow-results.png)
The green color of each of the bubbles indicates that step of the workflow was successful. Everything in this example, ran properly, but if not the color would appear red.


## Test Workflow

**Menu Access:** `Workflow` > `Test Workflow`

**Toolbar Icon:** ![](/images/analysis/heatmap.png)

The `Test Workflow` tool performs the user-configured workflow on a set of data, outputting a visual model to show the workflow steps, along with results of running all of the analysis tools in a selected file directory.

## FLIM Data Simulation Tuning
**Menu Access:** `Workflow` > `FLIM Data Simulation Tuning`

**Toolbar Icon:** ![](/images/analysis/heatmap.png)

The `FLIM Data Simulation Tuning` tool uses an autoencoder to first train a model, then apply that model to the original dataset to generate a larger simulated dataset. The Keck Center currently has this tool configured to output various plots and data tables to check the precision of the simulated data. This includes heatmaps and training loss plots. The results of the workflow are saved in the selected file directory.

## FLIM Feature Analysis

**Menu Access:** `Workflow` > `FLIM Feature Analysis`

**Toolbar Icon:** ![](/images/analysis/heatmap.png)

The `FLIM Feature Analysis` tool requires two datasets: one that is the larger simulated dataset from the `FLIM Data Simulation Tuning` tool, and the other being a real dataset. The tool is then trained on the simulated data and the resulting model is applied to the real data. Similar to PCA, this tool uses dimensionality reduction to generate feature values based on a particular data grouping. Unlike PCA, however, the `FLIM Feature Analysis` tool is nonlinear. The results of the workflow are saved in the selected file directory.
