# Gaussian Mixed Model

Like `K-Means`, the `Gaussian Mixed Model` tool groups data points into clusters. Unlike `K-Means`, it describes each cluster as a Gaussian (bell-shaped) distribution. Clusters can have different sizes, shapes and orientations. Each data point is assigned to a cluster, and also gets a probability of belonging to each cluster.

**Menu Access:** `Analysis` > `Gaussian Mixed Model`

**Toolbar Icon:** ![](/images/analysis/gmm.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front.

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Gaussian Mixed Model` menu.

3. In the `Configuration: Gaussian Mixed Model` dialog, select the features and the model settings:
    - `Features`: the numeric columns to cluster, e.g. `FAD a1`, `NAD(P)H a1`. Rows with a missing value in any of them are left out.
    - `Method`: `EM` (expectation maximization) fits a model with exactly the number of components (clusters) you set. `Variational Bayesian` treats that number as a maximum. It can leave some components empty or nearly empty, so it may find fewer clusters.
    - `Components`: the number of clusters (for `Variational Bayesian`: the maximum number).
    - `Covariance`: the shape of the clusters.
        - `full`: each cluster has its own shape and orientation.
        - `tied`: all clusters share the same shape.
        - `diag`: each cluster has its own shape, aligned with the feature axes.
        - `spherical`: round clusters, each with its own size.
    - `Random seed`: with a number, every run gives the same results. Leave it empty for different results on every run.

    ![](/images/analysis/gmm-config.png)

4. Click `OK`.

5. The results are shown in new data tables:
    - `GMM <covariance>, Feature Clustering`: the data, plus a category column `GMM <covariance>` with the cluster of each row. A column `GMM Prob Component <n>` for each cluster gives the probability that the row belongs to that cluster.
    - `GMM <covariance>, Component Information Criteria`: the BIC and AIC scores of models with 1 up to the chosen number of components. They help you choose the number of components (see below).
    - `GMM <covariance>, Covariance, component <n>`: one table per cluster with its covariance matrix, which describes how the features spread and vary together within the cluster.

## Choosing the Number of Components

Adding components always makes the model match the data more closely, even when the extra components only follow random noise. BIC (Bayesian Information Criterion) and AIC (Akaike Information Criterion) help find the number of components that describes the data well without adding components that aren't really there. Each gives a score for every number of components: how well the model matches the data, plus a penalty for every extra component.

How to read them:

- Lower is better. Pick the number of components with the lowest score, or the point where the scores stop dropping much (the "elbow" of the curve).
- BIC penalizes extra components more than AIC, especially for large tables. BIC tends to point to fewer components, AIC to more. If they disagree, BIC is the safer choice.
- Only compare scores from the same table, features and `Covariance` setting. A score on its own means nothing.

The scores are always calculated with the `EM` method, for 1 up to the chosen number of components, even when `Method` is `Variational Bayesian`.

## Example Output

Clusters of `FAD a1[%]` and `NAD(P)H a2[%]` with 3 components:
![](/images/analysis/gmm-results1.png)

BIC and AIC of 1 to 3 components:
![](/images/analysis/gmm-results2.png)

```{note}
To see the clusters, plot the data grouped by the `GMM <covariance>` column, e.g. with the `Scatter Plot` or the `Pair Plot`.
```
