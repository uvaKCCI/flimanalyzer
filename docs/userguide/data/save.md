# Saving Data

Data tables can be saved by clicking the `Save All Rows...` or `Save Shown Rows...` buttons in the table window. In the file dialog, choose the format: tab-separated text (`.txt`, the default) or comma-separated text (`.csv`). The ending is added if the file name doesn't have it. Column headers with several lines are saved on one line, with the lines separated by spaces. If a column name contains the format's separator (a tab or a comma) or has several lines, the GUI says so and asks whether to save anyway. After saving, the window is named after the saved file.

When you close a table window that has not been saved since it was made or changed, FLIMAnalyzer asks whether to save it. A file you opened counts as saved until you change it, for example with a filter.

* `Save All Rows...`: saves all the data, including rows hidden by filters.
* `Save Shown Rows...`: saves the data as currently displayed. Hidden rows are not saved and cannot be recovered from the saved file.