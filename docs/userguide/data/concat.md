# Concatenate

The `Concatenate` tool combines two or more data sets.

**Menu Access:** `Data` > `Concatenate`

**Toolbar Icon:** ![](/images/data/concatenate.png)

By default (`Direction`: `Rows (stack below)`), the `Concatenate` tool copies the data from the selected tables and creates a new data table where the tables are stacked, one above the other; a `Source` column holds the name of the table each row comes from. With `Direction`: `Columns (side by side)`, the columns of the tables are placed next to each other instead; `Numeric columns only` then takes only the numeric columns of all but the first table.

The following example configuration of the `Concatenate` tool will create a new table with all of the contents of example1.txt followed by the contents of example2.txt.

![](/images/data/concat-config1.png)
