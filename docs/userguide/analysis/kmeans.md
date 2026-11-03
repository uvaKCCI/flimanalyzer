# K-Means

The `K-Means` tool finds groups of similar data points (clusters). It works on the standardized features: each feature is rescaled to a mean of 0 and a standard deviation of 1, so that all features have the same weight.

**Menu Access:** `Analysis` > `K-Means`

**Tool panel icon:** ![](/images/analysis/kmeans.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front. The dialog's `Data` choice starts with this table; you can choose another one there (see [Choosing the data](/userguide/dialogs.md#choosing-the-data)).
    ![](/images/data/exdata_table.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `K-Means` menu.

3. In the `Configuration: K-Means` dialog, set:
    - `Clusters`: the number of clusters (default 2). To choose it, plot the data and look for groups, or use the elbow method: try different numbers of clusters and pick the point after which more clusters no longer improve the result much.
    - `Cluster column`: the name of the new column (default `Cluster`). The clusters are named after it: `Cluster 1`, `Cluster 2`, ...
    - `Initialization`: how the starting cluster centers are chosen. `k-means++` (default) places them far from each other, which usually gives a result faster. `random` picks them at random.
    - `Algorithm`: `lloyd` (default, the classic algorithm) or `elkan` (faster when the clusters are well separated, but uses more memory).
    - `Runs`: how many times the clustering is run, each time with different starting centers (default 4). The best result is kept.
    - `Max iterations`: the maximum number of steps in each run (default 300).
    - `Tolerance`: a run stops when the cluster centers of the standardized features change by less than this amount from one step to the next (default 0.0001).
    - `Random seed`: with a number (default 0), every run gives the same clusters. Leave it empty for different clusters on every run.
    - `Threads`, in the `Resources` section: see [Resources](/userguide/dialogs.md#resources).

4. Select the features. Rows with a missing value in any of them are left out. In the example, `FAD a1` and `NAD(P)H a1` are used, with 3 clusters.

    ![](/images/analysis/kmeans-config.png)

5. Click `OK`.

6. The results are shown in a new table window, `Table: K-Means`. It has the category columns, the selected features (with their original values) and the new category column `Cluster`, which gives the cluster of each data point. Other columns of the table are not included.

## Example Output

![](/images/analysis/kmeans-results1.png)

```{note}
To see the clusters, plot the data grouped by the `Cluster` column, e.g. with the [Scatter Plot](/userguide/plots/scatter).
```

The scatter plot of `FAD a1` and `NAD(P)H a1`, grouped by `Cluster`:

![](/images/analysis/kmeans-results2.png)
