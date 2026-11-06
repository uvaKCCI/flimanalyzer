# PCA

The `PCA` tool (principal component analysis) summarizes many features in a few new columns, the principal components. Each principal component is a weighted sum of the standardized features (features rescaled to a mean of 0 and a standard deviation of 1). `PC 1` captures the largest part of the variation (variance) in the data, `PC 2` the largest part of the variation that is left, and so on.

**Menu Access:** `Analysis` > `PCA`

**Tool panel icon:** ![](/images/analysis/pca.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front. The dialog's `Data` choice starts with this table; you can choose another one there (see [Choosing the data](/userguide/dialogs.md#choosing-the-data)).
    ![](/images/analysis/rf-start.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `PCA` menu.

3. In the `Configuration: PCA` dialog, set:
    - `Include the features` (unchecked by default): also include the original features in the result.
    - `Include standardized features` (checked by default): also include the standardized features in the result.
    - `Explained variance plot` (unchecked by default): a bar plot of the variance each component explains.
    - `Components`: a whole number (1 or more) is the number of components to keep. A number between 0 and 1 (not 0 or 1) is the fraction of the variance to explain: the default, 0.999, keeps as many components as needed to explain 99.9% of the variance. `1` means one component, not all of the variance. Leave it empty to keep all components.
    - `Random seed` (default 0): it only has an effect for tables with more than 500 features and a whole number of `Components`. Only then does scikit-learn use its randomized method, which depends on the seed. Otherwise every run gives the same result.

4. Select the features. Rows with a missing value in any of the selected features are left out. In the example, the amplitudes and lifetimes of FAD and NAD(P)H, and FLIRR, are used.

    ![](/images/analysis/pca-dialog.png)

5. Click `OK`.

6. The results are shown in three new table windows:
    - `Table: PCA Components`: one row per data point, with the category columns, the original features (if included), the standardized features (if included, named `<feature> standardized`) and the principal components `PC 1`, `PC 2`, ...
    - `Table: PCA Explained`: for each component (`PC`), the fraction of the variance it explains (`explained var ratio`).
    - `Table: PCA Eigen`: one row per component, with the weight of each feature in that component.

    If `Explained variance plot` is checked, the explained variance is also plotted, in `Plot: PCA Explained Plot`.

## Example Output

![](/images/analysis/pca-res.png)

The explained variance of each component:

![](/images/analysis/pca-hist.png)
