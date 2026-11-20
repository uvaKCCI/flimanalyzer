# Adjusting Precision

The `Precision` field in each table window sets the number of decimal places shown in columns of decimal numbers, also for the whole numbers in them (`2` shows as `2.000`). Columns of integers are not changed. It can be set from 1 to 10; the default is `3`, which shows three decimal places.

![](/images/data/precision.png)

**Note:** Changing the `Precision` value changes only how numbers are shown. The data values themselves are not changed.

## Other controls of the table window

* `Autosize Cols` makes each column as wide as its contents.
* `Pivot...` and `Unpivot...` open the [Pivot](pivot.md) and [Unpivot](unpivot.md) dialogs for the window's table (the rows it shows).
* Double-click the header of a category column to rename its values. In the `<column>: Pattern Rename` dialog, enter a pattern (a regular expression) under `Pattern match` and the text that replaces it under `Replacement`. The pattern is replaced in every value of the column. The default pattern `^0+` removes leading zeros, so `007` becomes `7`. If the pattern or the replacement is not valid, for example `\1` without a group in the pattern, a message shows the problem and the values stay as they are.
