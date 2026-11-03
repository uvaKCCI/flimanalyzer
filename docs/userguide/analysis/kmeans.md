# K-Means

The `K-Means` tool finds groups of similar data points (clusters). It works on the standardized features: each feature is rescaled to a mean of 0 and a standard deviation of 1, so that all features have the same weight.

**Menu Access:** `Analysis` > `K-Means`

**Toolbar Icon:** ![](/images/analysis/kmeans.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front.
    ![](/images/data/exdata_table.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `K-Means` menu.

3. In the `Configuration: K-Means` dialog, set:
    - `Clusters`: the number of clusters. To choose it, plot the data and look for groups, or use the elbow method: try different numbers of clusters and pick the point after which more clusters no longer improve the result much.
    - `Initialization`: how the starting cluster centers are chosen. `k-means++` places them far from each other, which usually gives a result faster. `random` picks them at random.
    - `Algorithm`: `lloyd` (the classic algorithm) or `elkan` (faster when the clusters are well separated, but uses more memory).
    - `Runs`: how many times the clustering is run, each time with different starting centers. The best result is kept.
    - `Max iterations`: the maximum number of steps in each run.
    - `Tolerance`: a run stops when the cluster centers change by less than this amount from one step to the next.
    - `Cluster column`: the name of the new column. The clusters are named after it: `Cluster 1`, `Cluster 2`, ...
    - `Random seed`: with a number, every run gives the same clusters. Leave it empty for different clusters on every run.

4. Select the features. In the example, `FAD a1` and `NAD(P)H a1` are used, with 3 clusters.

    ![](/images/analysis/kmeans-config.png)

5. Click `OK`.

6. The results are shown in a new data table. Its new category column `Cluster` gives the cluster of each data point.

## Example Output

![](/images/analysis/kmeans-results1.png)

```{note}
To see the clusters, plot the data grouped by the `Cluster` column, e.g. with the [Scatter Plot](/userguide/plots/scatter).
```

The scatter plot of `FAD a1` and `NAD(P)H a1`, grouped by `Cluster`:

![](/images/analysis/kmeans-results2.png)
