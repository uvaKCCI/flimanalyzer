# Concatenate

The `Concatenate` tool combines two or more data tables.

**Menu Access:** `Data` > `Concatenate`

**Toolbar Icon:** ![](/images/data/concatenate.png)

By default (`Direction`: `Rows (stack below)`), the `Concatenate` tool copies the rows of the selected tables into a new data table, one table below the other. A `Source` column shows which table each row comes from. With `Direction`: `Columns (side by side)`, the columns of the tables are placed next to each other instead. In this case, `Numeric columns only` adds only the numeric columns of the second and later tables. The first table keeps all its columns. Without it, all columns are added; a column whose name is already taken gets the name of its table, e.g. `Treatment (example2.txt)`.

In the `Configuration: Concatenate` dialog, check the open tables to concatenate under `Tables`. With the settings below, the tool creates a new table with all rows of `example1.txt`, followed by all rows of `example2.txt`.

![](/images/data/concat-config1.png)
