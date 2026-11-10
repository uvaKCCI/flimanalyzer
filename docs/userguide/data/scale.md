# Scale

The `Scale` tool scales the selected features, so that features with different units or ranges can be compared, or used by later tools. The scaled features are added to the table as new columns, named after the feature and the method, for example `NAD(P)H t1 standardized`.

**Menu Access:** `Data` > `Scale`

1. Select `Data` > `Scale`.

2. In the `Configuration: Scale` dialog, set:

    - `Features`: the columns to scale (at least one).
    - `Method`:
        - `standardize` (default): mean 0 and standard deviation 1. This is the same scaling as `Standardize input` in `PCA`, `K-Means` and `Gaussian Mixed Model`.
        - `min-max`: from 0 (the smallest value) to 1 (the largest).
        - `robust`: median 0 and interquartile range 1. Less affected by outliers than `standardize`.
    - `Grouping`: scale within each group of these columns, for example per `FOV`, so that each field of view is scaled on its own. Without a grouping, the whole table is scaled at once. Rows without a value in a grouping column form a group of their own.
    - `Keep the original features` (checked by default): add the scaled features as new columns. Unchecked, the scaled columns replace the original ones, in their place. A scaled column whose name the table already has, for example when a feature is scaled twice, gets a number: `t1 standardized_1`.

3. Click `OK`.

The result is `Table: Scaled`, with all columns of the input table and the scaled features. The new columns are named after the method: `<feature> standardized`, `<feature> min-max` or `<feature> robust`. Missing values stay missing.
