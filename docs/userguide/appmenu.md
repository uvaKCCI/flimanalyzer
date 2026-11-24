# Menus

The tool panel, the main window of FLIMAnalyzer, has a group of icons for each menu: `File` (open and import data), `Data`, `Analysis`, `Plot` and `Workflow`. The last group, `Monitor`, has the entries of the `Monitor` menu. Hover the mouse over an icon to see the name of its tool. Each icon does the same as the menu entry of the same name. To show only the tools and workflows you use, choose them with `File` > `Favorites...`.

## File

### Open Tables...

Opens data files, each in a table window. See [Loading Data](/userguide/data/load).

### Import Tables...

Reads data files and runs a workflow on the tables. See [Loading Data](/userguide/data/load).

### Import

A submenu with the workflow files that are placed in the `File` menu, for example the built-in `Import` workflow. A workflow file chooses its menu, and a submenu if any, with its `category` (see [Workflow files](/userguide/workflows.md#workflow-files)).

### Save All Windows...

Saves all open tables and plots in one step. See [Saving all windows](/userguide/data/save.md#saving-all-windows).

### Import Settings...

Loads settings from a file for this session. See [Saving and loading all settings](/userguide/settings.md#saving-and-loading-all-settings).

### Export Settings...

Saves the settings in use now to an app settings file: the range filters, the settings of each tool and the app settings. See [Saving and loading all settings](/userguide/settings.md#saving-and-loading-all-settings).

### Favorites...

Chooses which tools and workflows the tool panel shows, and in which order: check them, and move them with `Up` and `Down`. The tool panel then shows only these, each in the group of its menu. Groups without favorites are left out; `File` always shows `Open Tables` and `Import Tables`. A workflow file's icon goes to the group of its menu, for example the `File` group for the built-in `Import` workflow; a workflow file without a menu goes to `Workflow`.

With no favorites checked, the tool panel shows all tools, grouped by menu, but no workflow files: those are always in the menus, and in the tool panel only as favorites. The GUI writes your choice to the user settings file (`favorites`, see [Settings](/userguide/settings)); the menus always list all tools.

### Settings...

Shows the app settings of this session: the results folder, the executor, the Prefect server, the server timeout and the log folder. For each, it shows where its value comes from and how to change it. On macOS it is in the `FLIMAnalyzer` menu. See [Viewing the app settings](/userguide/settings.md#viewing-the-app-settings).

### Exit

Closes FLIMAnalyzer. On macOS it is `Quit FLIMAnalyzer` in the `FLIMAnalyzer` menu (⌘Q). If table or plot windows have unsaved results, FLIMAnalyzer lists them and asks first, also when you log out or shut down the computer (where the system lets it ask):

* `Cancel` keeps everything open.
* `Review...` asks for each window in turn: `Save`, `Don't Save`, or `Cancel`, which stops quitting.
* `Save All Windows...` saves them all (see [Saving all windows](/userguide/data/save.md#saving-all-windows)), then quits; if you cancel it, or a window cannot be saved, FLIMAnalyzer stays open.
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

### Workflows defined in code

The built-in workflows, such as `Basic FLIRR Analysis`.

### Workflow files

Below them: the workflow files placed in the `Workflow` menu, or in a submenu of it, and those placed in no menu. A workflow file can also be placed in another menu, for example `Analysis` or `Data` > `Reshape`; it is then there instead (see [Workflow files](/userguide/workflows.md#workflow-files)).

### Run Workflow File...

The last entry: runs a workflow file you choose on the table of the current window (see [Running a workflow file in the GUI](/userguide/workflows.md#running-a-workflow-file-in-the-gui)).

## Using the tools

The tools of the `Data`, `Analysis`, `Plot` and `Workflow` menus are always available. They open their dialog (see [Tool dialogs](/userguide/dialogs)) once a table window is open; without one, a message asks you to open or import data first.

## Monitor

The `Monitor` menu opens pages that show the runs, in the web browser. Menu entries that open a page in the web browser end with ↗, here and `Help` > `Documentation`; in the tool panel, the ↗ is in their tooltips.

### Prefect Server

Opens the Prefect server in the web browser, with all runs and their tasks (see [Prefect server](/install/index.md#prefect-server)).

### Last Run

Opens the page of the last run the GUI started, even if it failed or was cancelled. The GUI keeps it in the user settings file (`last_run_url`), so it is also available after a restart. Until the GUI has started a run on a Prefect server, `Last Run` is not available.

## Window

### Open windows

The menu lists all open windows (table windows and plot windows). Select one to bring it to the front. On macOS, the system makes this list, as in other Mac apps: it also shows the main window and marks the window in front.

### Close all windows

Closes all table and plot windows.

## Help

### Documentation

Opens the documentation of the installed version (for a development version: the latest documentation).

### About FLIMAnalyzer

Shows the version. On macOS it is in the `FLIMAnalyzer` menu.
