# Menus

The tool panel, the main window of FLIMAnalyzer, has a group of icons for each menu: `File` (open and import data), `Data`, `Analysis`, `Plot` and `Workflow`. The last group, `Monitor`, has the entries of the `Monitor` menu. Hover the mouse over an icon to see the name of its tool. Each icon does the same as the menu entry of the same name. To show only the tools and workflows you use, choose them with `File` > `Favorites...`.

## File

* `Open Tables...` opens data files, each in a table window; `Import Tables...` reads data files and runs a workflow on the tables. See [Loading Data](/userguide/data/load).
* Below `Import Tables...`: the workflow files whose `category` names the `File` menu, in the menu or in the submenu that their `category` names, for example `File` > `Import` with the built-in `Import` workflow (see [Workflow files](/userguide/workflows.md#workflow-files)).
* `Save All Windows...` saves all open tables and plots in one step. See [Saving all windows](/userguide/data/save.md#saving-all-windows).
* `Import Settings...` loads settings from a file for this session. `Export Settings...` saves all settings as they are active now, whatever they come from, to an app settings file: the range filters, the settings of each tool and the app settings. See [Saving and loading all settings](/userguide/settings.md#saving-and-loading-all-settings).
* `Favorites...` chooses the tools and workflows the tool panel shows, and their order: check them and move them with `Up` and `Down`. The tool panel then shows only them, each in the group of its menu, in the order you chose; groups without favorites are left out, and `File` always shows `Open Tables` and `Import Tables`. A workflow file's icon goes to the group of the menu that its `category` names, for example the `File` group for `["File", "Import"]`; without `category`, to `Workflow` (see [Workflow files](/userguide/workflows.md#workflow-files)). With none checked, it shows all tools, grouped by menu, without the workflow files (built-in or your own): they are in the menus, and in the tool panel only as favorites. The GUI writes your choice to the user settings file (`favorites`, see [Settings](/userguide/settings)); the menus always list all tools.
* `Settings...` shows the app settings of this session: the results folder, the executor, the Prefect server, the server timeout and the log folder. For each, it shows where its value comes from and how to change it. On macOS it is in the `FLIMAnalyzer` menu. See [Viewing the app settings](/userguide/settings.md#viewing-the-app-settings).
* `Exit` closes FLIMAnalyzer. On macOS it is `Quit FLIMAnalyzer` in the `FLIMAnalyzer` menu (⌘Q). If table or plot windows have unsaved results, FLIMAnalyzer lists them and asks first, also when you log out or shut down the computer (where the system lets it ask):
  * `Cancel` keeps everything open.
  * `Review...` asks for each window in turn: `Save`, `Don't Save`, or `Cancel`, which stops quitting.
  * `Save All Windows...` saves them all (see [Saving all windows](/userguide/data/save.md#saving-all-windows)), then quits; if you cancel it, or a window can't be saved, FLIMAnalyzer stays open.
  * `Discard All` quits, and the unsaved results are lost.

  A table you opened from a file, and results that a tool saved when it ran, count as saved until you change them. Plots count as changed after you edit an axis, a label or a line.

## Data

The `Data` menu has the tools that change or combine data tables, such as `Sort`, `Filter`, `Split` and `Concatenate`. See [Data Tables](/userguide/data/index).

## Analysis

The `Analysis` menu has the analysis tools, and the workflow `Autoencoder Train`. See [Analysis](/userguide/analysis/index).

## Plot

The `Plot` menu has the plots. See [Plots](/userguide/plots/index).

## Workflow

The `Workflow` menu runs several tools in one run. See [Workflows](/userguide/workflows).

* The workflows defined in code, such as `Basic FLIRR Analysis`.
* The workflow files without `category`, and those whose `category` names the `Workflow` menu, below the workflows defined in code, or in the submenu that their `category` names. A workflow file whose `category` names another menu, for example `Analysis` or `["Data", "Reshape"]`, is in that menu or submenu instead (see [Workflow files](/userguide/workflows.md#workflow-files)).
* `Run Workflow File...`, the last entry: runs a workflow file you choose on the table of the current window (see [Running a workflow file in the GUI](/userguide/workflows.md#running-a-workflow-file-in-the-gui)).

The tools of the `Data`, `Analysis`, `Plot` and `Workflow` menus are always available. They open their dialog (see [Tool dialogs](/userguide/dialogs)) once a table window is open; without one, a message asks you to open or import data first.

## Monitor

The `Monitor` menu opens pages that show the runs, in the web browser. Menu entries that open a page in the web browser end with ↗, also `Help` > `Documentation`; the tool panel shows the ↗ in their tooltips.

- `Prefect Server` opens the Prefect server in the web browser, with all runs and their tasks (see [Prefect server](/install/index.md#prefect-server)).
- `Last Run` opens the page of the last run the GUI started, also if it failed or was cancelled. The GUI keeps it in the user settings file (`last_run_url`), so it is also available after a restart. Until the GUI has started a run on a Prefect server, `Last Run` is not available.

## Window

The `Window` menu lists all open windows (table windows and plot windows). Select one to bring it to the front. `Close all windows` closes them. On macOS, the system makes this list, as in other Mac apps: it also shows the main window and marks the window in front.

## Help

* `Documentation` opens the documentation of the installed version (for a development version: the latest documentation).
* `About FLIMAnalyzer` shows the version. On macOS it is in the `FLIMAnalyzer` menu.
