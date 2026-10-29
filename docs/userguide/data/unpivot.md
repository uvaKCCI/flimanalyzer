# Unpivoting Data

**Menu Access:** `Data` > `Unpivot`

**Toolbar Icon:** ![](/images/data/unpivot.png)

Unpivoting is the inverse of [pivoting](pivot.md): it moves one line of the column headers back into a category column.

Column headers made by tools can have several lines, one per *level*. Pivoting the `Treatment` column gives headers such as `FLIRR` / `ctrl` (line 1: the feature, line 2: the treatment); a summary gives headers such as `FLIRR` / `mean` (line 1: the feature, line 2: the statistic). The tools that make such headers record the names of their levels (`Feature`, `Treatment`, `Statistic`).

1. Select `Data` > `Unpivot`.

2. Under `Columns`, check the columns to unpivot (they need the same number of header lines).

3. Under `Level`, select the header line that becomes the category column. Each line is shown with its name and some of its values, e.g. `Treatment: ctrl, Dox15, ...`. The last line is selected by default.

4. Optionally, enter a name for the new category column under `Category column`; by default it is named after the level.

5. Click `Ok`.

For example, unpivoting the level `Treatment` of the columns `FLIRR` / `ctrl`, `FLIRR` / `Dox15`, `t1` / `ctrl` and `t1` / `Dox15` gives a category column `Treatment` (`ctrl`, `Dox15`) and the value columns `FLIRR` and `t1`: the table before pivoting. Unpivoting the level `Feature` instead gives a category column `Feature` (`FLIRR`, `t1`) and the value columns `ctrl` and `Dox15`.

Columns with a single header line are stacked: their names go into a category column `Feature`, their values into a column `Value`.

Level names are kept with the table while the application runs, but not in saved text files. For a table read from a file, the levels are named by their position: `Feature`, `Level 2`, `Level 3`, ...
