# PCA

The `PCA` tool (principal component analysis) summarizes many features in a few new columns, the principal components. Each principal component is a weighted sum of the standardized features (features rescaled to a mean of 0 and a standard deviation of 1). `PC 1` captures the largest part of the variation (variance) in the data, `PC 2` the largest part of the variation that is left, and so on.

**Menu Access:** `Analysis` > `PCA`

**Toolbar Icon:** ![](/images/analysis/pca.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front.
    ![](/images/analysis/rf-start.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `PCA` menu.

3. In the `Configuration: PCA` dialog, set:
    - `Components`: the number of components, or the fraction of the variance to explain (0 to 1). The default, 0.999, keeps as many components as needed to explain 99.9% of the variance. Leave it empty to keep all components.
    - `Include the features`: also include the original features in the result.
    - `Include standardized features`: also include the standardized features in the result.
    - `Explained variance plot`: a bar plot of the variance each component explains.
    - `Random seed`: with a number, every run gives the same results.

4. Select the features. In the example, the amplitudes and lifetimes of FAD and NAD(P)H, and FLIRR, are used.

    ![](/images/analysis/pca-dialog.png)

5. Click `OK`.

6. The results are shown in three new data tables. `PCA Components` has the principal components of each data point (and the features, if included). `PCA Explained` has the variance each component explains. `PCA Eigen` has the weight of each feature in each component. If `Explained variance plot` is checked, the explained variance is also plotted, in a plot window.

## Example Output

![](/images/analysis/pca-res.png)

The explained variance of each component:

![](/images/analysis/pca-hist.png)
