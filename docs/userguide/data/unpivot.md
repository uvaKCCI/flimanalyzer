# Unpivoting Data

**Menu Access:** `Data` > `Unpivot`

**Tool panel icon:** ![](/images/data/unpivot.png)

Unpivoting reverses [pivoting](pivot.md): it moves one line of the column headers back into a category column.

Column headers made by tools can have several lines, one per *level*. Pivoting the `Treatment` column gives headers such as `FLIRR` / `ctrl` (line 1: the feature, line 2: the treatment); a summary gives headers such as `FLIRR` / `mean` (line 1: the feature, line 2: the statistic). The tools that make such headers record the names of their levels (`Feature`, `Treatment`, `Statistic`).

1. Select `Data` > `Unpivot`, or click `Unpivot...` in the table window to unpivot its table (the dialog opens with it selected).

2. Under `Columns`, check the columns to unpivot.

3. Under `Level`, select the header line that becomes the category column. Each line is shown with its name and some of its values, for example `Treatment: ctrl, Dox15, ...`. The last line is selected by default.

4. Optionally, enter a name for the new category column under `Category column`; by default it is named after the level.

    A column with fewer header lines than the others, for example `FLIRR` next to `FLIRR` / `standardized` after [Scale](/userguide/analysis/scale.md) with `Keep original` checked, counts as having empty last lines. In the new category column, its rows get the value of `Label for a missing line` (default `none`; for example `original`). The dialog warns which columns have fewer lines. With `Category column` `Scaling mode` and the label `original`, the table has one `FLIRR` column and `Scaling mode` `original` or `standardized`.

5. Click `OK`.

For example, unpivoting the level `Treatment` of the columns `FLIRR` / `ctrl`, `FLIRR` / `Dox15`, `t1` / `ctrl` and `t1` / `Dox15` gives a category column `Treatment` (`ctrl`, `Dox15`) and the value columns `FLIRR` and `t1`: the table before pivoting. Unpivoting the level `Feature` instead gives a category column `Feature` (`FLIRR`, `t1`) and the value columns `ctrl` and `Dox15`.

Columns with a single header line are stacked: their names go into a category column `Feature`, and their values into a column `Value` (`Value_1` if a category column is already named `Value`).

Level names are kept with the table while FLIMAnalyzer is open, but not in saved text files. FLIMAnalyzer saves headers of several lines on one line, with the lines separated by spaces (see [Saving Data](save.md)), so a table it saved and read back has no levels to unpivot. For a table read from a file whose headers have line breaks, for example one made by another program, the levels are named by their position: `Feature`, `Level 2`, `Level 3`, ...
