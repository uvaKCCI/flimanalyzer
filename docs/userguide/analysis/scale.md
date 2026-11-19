# Scale

The `Scale` tool scales the selected features, so that features with different units or ranges can be compared, or used by later tools. The scaled features are added to the table as new columns, named after the feature and the method, for example `NAD(P)H t1` / `standardized` (a header of two lines: the feature, then the method).

**Menu Access:** `Analysis` > `Scale`

**Tool panel icon:** ![](/images/analysis/scale.png)

1. Select `Analysis` > `Scale`.

2. In the `Configuration: Scale` dialog, set:

    - `Features`: the columns to scale (at least one).
    - `Method`:
        - `standardize` (default): mean 0 and standard deviation 1. This is the same scaling as `Standardize input` in `PCA`, `K-Means` and `Gaussian Mixed Model`.
        - `min-max`: from 0 (the smallest value) to 1 (the largest).
        - `robust`: median 0 and interquartile range 1. Less affected by outliers than `standardize`.
    - `Grouping`: scale within each group of these columns, for example per `FOV`, so that each field of view is scaled on its own. Without a grouping, the whole table is scaled as one group. Rows without a value in a grouping column form a group of their own.
    - `Keep the original features` (checked by default): add the scaled features as new columns. Unchecked, the scaled columns replace the original ones, in their place. A scaled column whose name the table already has, for example when a feature is scaled twice, gets a number: `t1` / `standardized_1`.

    Below the settings, the dialog shows the first rows of up to three features before and after scaling, in a small table. The whole table is scaled for it, so the values are those the tool makes.

3. Click `OK`.

The result is `Table: Scaled`, with the columns of the input table and the scaled features. With `Keep the original features` checked, the scaled features are added after the last column; unchecked, they replace the original features, in their places. The new columns are named after the method, with two header lines: `<feature>` / `standardized`, `<feature>` / `min-max` or `<feature>` / `robust`. Missing values stay missing.
