# Saving Data

Data tables can be saved by clicking the `Save All Rows...` or `Save Shown Rows...` buttons in the table window. In the file dialog, choose the format: tab-separated text (`.txt`, the default) or comma-separated text (`.csv`). The extension is added if the file name doesn't have it. Column headers with several lines are saved on one line, with the lines separated by spaces. If a column name contains the format's separator (a tab or a comma) or has several lines, the GUI says so and asks whether to save anyway. After saving, the window is named after the saved file.

The suggested file name is the window's title, changed so that it is a safe file name: spaces, `[`, `]`, `(` and `)` are removed, `,`, `/` and `\` become `_`, `:` becomes `-`, and `%` becomes `perc`.

When you close a table window that has not been saved since it was made or changed, the GUI asks whether to save it. A file you opened counts as saved until you change it, for example with a filter. This save works like `Save All Rows...`: it saves all rows, also those hidden by filters. The suggested file name is the window's title, changed as above.

* `Save All Rows...`: saves all the data, including rows hidden by filters.
* `Save Shown Rows...`: saves the data as currently displayed. Hidden rows are not saved and cannot be recovered from the saved file.

## Saving all windows

**Menu Access:** `File` > `Save All Windows...`

Saves all open tables and plots at once. Choose a folder and the formats (see [Saving results](/userguide/dialogs.md#saving-results) for the formats). The windows are saved in a new folder, named after the date and time, in the folder you chose, so earlier files are never overwritten. Tables are saved with all their rows, also those hidden by filters. The files are named after the windows; if two names would be the same file (for example `cells` and `Cells`), `-2`, `-3` and so on are added.

The dialog opens at the folder you last used for it in this session, otherwise at the default results folder. Choosing a folder here doesn't change the default results folder. Afterwards, the saved windows count as saved, and a message lists any window that could not be saved.
