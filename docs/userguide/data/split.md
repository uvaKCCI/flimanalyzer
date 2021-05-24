# Splitting Data

In some cases it may be desirable to split datasets into non-overlapping subsets based on categorical groups. The table has four categorical columns, `Cell`, `Compartment`, `FOV` (field-of-view), and `Treatment`. 

Follow these steps to split this table into a set of tables where each resulting table contains the data corresponding to a specific `FOV`.

1. Click the `Split` button in the data table's sidebar.

2. In the next `Split Data` dialog window, select the `FOV` option. Leave the other options unselected.

    ![](/images/data/split-input.png)

3. Click `Ok`.

The `FOV` column in the original table contained five distinct values: `a`, `b`, `c`, `d`, and `e`. The split operation creates five new tables, one for each of the `FOV` labels.
 
![](/images/data/split-result.png)