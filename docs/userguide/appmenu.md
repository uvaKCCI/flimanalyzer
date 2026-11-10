# Menus

The tool panel, the main window of FLIMAnalyzer, has a group of icons for each menu: `File` (open and import data), `Data`, `Analysis`, `Plot` and `Workflow`. Hover the mouse over an icon to see the name of its tool. Each icon does the same as the menu entry of the same name.

## File

* `Open...` and `Import...` load data files. See [Loading Data](/userguide/data/load).
* `Save All Windows...` saves all open tables and plots at once. See [Saving all windows](/userguide/data/save.md#saving-all-windows).
* `Import Settings...` and `Export Settings...` load and save all settings: the range filters and the settings of each tool, including those of `Import...`. See [Settings](/userguide/settings).
* `Settings...` shows the app settings of this session: the results folder, the executor, the Prefect server, the log folder and how workflows handle missing columns. For each, it shows where its value comes from and how to change it. On macOS it is in the `FLIMAnalyzer` menu. See [Viewing the app settings](/userguide/settings.md#viewing-the-app-settings).
* `Exit` closes FLIMAnalyzer. On macOS it is `Quit FLIMAnalyzer` in the `FLIMAnalyzer` menu (⌘Q). If table or plot windows have unsaved results, FLIMAnalyzer lists them and asks first, also when you log out or shut down the computer (where the system lets it ask):
  * `Cancel` keeps everything open.
  * `Review...` goes through the windows one by one: `Save`, `Don't Save`, or `Cancel`, which stops quitting.
  * `Save All Windows...` saves them all (see [Saving all windows](/userguide/data/save.md#saving-all-windows)), then quits; if you cancel it, or a window can't be saved, FLIMAnalyzer stays open.
  * `Discard All` quits, and the unsaved results are lost.

  A table you opened from a file, and results that a tool saved when it ran, count as saved until you change them. Plots count as changed after you edit an axis, a label or a line.

## Data

The `Data` menu has the tools that change or combine data tables, such as `Sort`, `Filter`, `Split` and `Concatenate`. See [Data Tables](/userguide/data/index).

## Analysis

The `Analysis` menu has the analysis tools. See [Analysis](/userguide/analysis/index).

## Plot

The `Plot` menu has the plots. See [Plots](/userguide/plots/index).

## Workflow

The `Workflow` menu runs several tools in one go. See [Workflows](/userguide/workflows).

The tools of the `Data`, `Analysis`, `Plot` and `Workflow` menus are always available. They open their dialog (see [Tool dialogs](/userguide/dialogs)) once a table window is open; without one, a message asks you to open or import data first.

## Window

The `Window` menu lists all open windows (table windows and plot windows). Select one to bring it to the front. `Close all windows` closes them.

## Help

* `Documentation` opens the documentation of the installed version (for a development version: the latest documentation).
* `About FLIMAnalyzer` shows the version. On macOS it is in the `FLIMAnalyzer` menu.
