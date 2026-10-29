# Splitting Data

In some cases it may be desirable to split datasets into non-overlapping subsets based on categorical groups. The table has four categorical columns, `Cell`, `Compartment`, `FOV` (field-of-view), and `Treatment`. 

**Menu Access:** `Data` > `Split`

Follow these steps to split this table into a set of tables where each resulting table contains the data corresponding to a specific `FOV`.

1. Select `Data` > `Split`.

2. In the `Split` dialog window, check `FOV` under `Split by`. Leave the other options unchecked.

    ![](/images/data/split-input.png)

3. Click `Ok`.

The `FOV` column in the original table contained five distinct values: `a`, `b`, `c`, `d`, and `e`. The split operation creates five new tables, one for each of the `FOV` labels, named after their values (e.g. `Table: Split: FOV=a`). With several columns checked, there is a table for each combination of their values that occurs in the data.
 
![](/images/data/split-result.png)