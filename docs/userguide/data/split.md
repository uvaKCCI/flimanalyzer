# Splitting Data

Sometimes it is useful to split a data table into separate tables, one for each group in the category columns. Each row goes into exactly one of the new tables. The example table has three category columns, `Treatment`, `FOV` (field-of-view), and `Cell`.

**Menu Access:** `Data` > `Split`

**Toolbar Icon:** ![](/images/data/split.png)

Follow these steps to split this table into a set of tables where each resulting table contains the data corresponding to a specific `FOV`.

1. Select `Data` > `Split`.

2. In the `Configuration: Split` dialog, check `FOV` under `Split by`. Leave the other options unchecked.

    ![](/images/data/split-input.png)

3. Click `OK`.

The `FOV` column in the original table contains five different values: `a`, `b`, `c`, `d`, and `e`. Splitting creates five new tables, one for each `FOV` value. Each table is named after its value, for example `Table: Split: FOV=a`. With several columns checked, there is a table for each combination of their values that occurs in the data.

The table of `FOV` `a`:

![](/images/data/split-result.png)