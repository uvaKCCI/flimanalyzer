# Moving from 0.6 to 0.7

This page is for users of FLIMAnalyzer 0.6. It lists what you must do, and what you can do, when you change to 0.7. The full list of changes is in the changelog (`CHANGELOG.md`, section `0.7.0`).

In short:

* Your settings files of 0.6 still work. 0.7 converts them when it reads them; 0.6 can't read the files that 0.7 writes.
* `flimbatch` needs `--run`, and reads each data file into a table of its own.
* Tool settings for `flimbatch` go in tool files, not in the app settings file.
* Workflows are strict by default, also in the GUI.
* Some results change, because of bug fixes.
* The names of saved files and folders follow a new rule.

## Requirements

* Python 3.12 to 3.14.
* PyTorch 2.14.1. Installs with uv from the source and the Docker CUDA image use CUDA 13.0, which needs NVIDIA driver 580 or newer and a GPU of the Turing generation or newer. For older GPUs, see [PyTorch and the GPU](/install/index.md#pytorch-and-the-gpu).

## Settings files of 0.6

You don't have to change your settings files. Each time FLIMAnalyzer reads a settings file of 0.5 or 0.6, it converts the settings to the current format in memory, and the file stays as it is (see [Settings files from older versions](/userguide/settings.md#settings-files-from-older-versions)).

* **Update the file, if you want.** When the GUI uses a file of an older version, it asks whether to update it. `Update` rewrites the file in the current format and keeps the original next to it, for example `lab.v1.json`. FLIMAnalyzer 0.6 can still read the original; it can't read the updated file. `flimsettings app --update FILE` and `flimsettings tool --update FILE` do the same from the command line (see [The flimsettings command](/userguide/flimsettings)). `flimbatch` never changes a settings file.
* **Validate the file.** 0.7 validates each settings file before it uses it. A file with unknown settings or invalid values is not used. `flimsettings app --validate FILE` lists the problems of a file, and the settings that were converted.
* **The user settings file is new.** The GUI now saves the settings you change automatically, in `usersettings.json` (see [The user settings file](/userguide/settings.md#the-user-settings-file)). `Import Settings...` applies a file to the session only. `flimbatch` doesn't read the user settings file.
* **`defaults.json` is deprecated.** The GUI started without `-s` still uses a `defaults.json` in the start folder, with a warning. Move the file to a folder of the app settings search path, give it a name, for example `cells.json`, and start with `-s cells` (see [App settings files](/userguide/settings.md#app-settings-files)). From 0.8.0, `defaults.json` is not read.
* **A workflow's `Strict` is now `processing.strict`.** The `strict` setting that 0.6 saved for a workflow moves to its `processing` > `strict` when the file is read; `null` (automatic) becomes strict. See [Workflows in the GUI](#workflows-in-the-gui).
* **`-s` takes app settings files only.** A tool file or a workflow file given with `-s` is an error.

## The import settings of 0.6

The `Import` dialog of 0.6 is removed. `File` > `Open Tables...` opens each file in a table window, and `File` > `Import Tables...` reads the files and runs a workflow file on them (see [Import Tables](/userguide/data/load.md#import-tables)). The built-in `Import` workflow renames and drops the channels' columns, joins the tables and calculates the FLIM features, as `Import...` did with the default settings.

The `import` section of a 0.6 settings file (delimiter, filename parser, patterns, files left out, column combinations) is not used any more:

* **In the GUI:** when the GUI uses such a file (with `-s`, at startup, or with `File` > `Import Settings...`), it offers to save these settings as a workflow file that imports as 0.6 did, for example `Import (lab-settings)`. Save it to keep your import settings. Nothing is applied unless you save it.
* **In `flimbatch`:** it says that the import settings are not used. Open the file once in the GUI and save the workflow file.

Also note:

* Categories from file names are now a `Separate Categories` step. Its presets are the filename parsers of 0.6, for example `FOV, Treatment, Cell` (see [Separate Categories](/userguide/data/separate.md#presets)).
* In a saved import workflow file, combined categories are joined with `:` instead of `-`, for example `FOV:Treatment` = `FOV1:WT` instead of `FOV-Treatment` = `FOV1-WT`.
* The columns keep the order of the files, after `Source`, `Directory` and `File`; calculated columns are added at the end. In 0.6 the columns were sorted alphabetically.
* Each table read from a file gets the column `Source`, the file as a URI. The columns `Directory` and `File` are deprecated and are no longer added from 0.8.0. To add `Source` to tables imported with 0.6, use [Directory/File to Source](/userguide/data/source).

## Batch mode

`flimbatch` works differently in 0.7. Check your scripts against this list (see [Batch Mode](/userguide/batch)).

* **`--run` is necessary.** In 0.6, `flimbatch` without `--run` imported all files into one table and saved `Imported.txt`. Now each file given with `-i` is read into a table of its own, and nothing is done without `--run`.
* **One imported table:** use `--run Import`. To run a tool on the imported table, use a workflow file that starts with the steps of `Import`. To make one, print the built-in file, give it another `name` and add your steps:

  ```
  flimsettings workflow --show import > my-import.json
  ```

* **Tool settings in tool files.** `flimbatch --run NAME` with the tool's settings in the `-s` file is deprecated and is removed in 0.8.0. Save the tool's settings as a tool file (`Save Settings...` in the tool's dialog, or `flimsettings tool --show NAME` and edit the output), and run it with `--run FILE`:

  ```
  # 0.6
  flimbatch -i data/ -o results/ -c settings.json --run Summarize
  # 0.7
  flimbatch -i data/ -o results/ --run summary.json
  ```

  A tool given to `--run` runs once on each table, not once on all files. An `-s` file that has no settings for the tool given to `--run NAME` is an error; in 0.6 the tool ran with its defaults.
* **No range filters.** `flimbatch` no longer filters the data with the range filters of the table windows (`filters` > `use`). To filter rows, add a `Filter` step to a workflow file.
* **New results layout.** Each call saves in one folder, `<output>/<date and time>/`, with a folder `run-<n>` for each `--run`, in the order given. Each `run-<n>` folder holds `run_summary.txt`, `resolved.json` and a folder for each step, `<id>-<tool>`, for example `01-Summarize`. A tool given to `--run` is step `01`. In 0.6 the results were in `<output>/<tool>/<date and time>/`. Update scripts that read the result files.
* **`flimbatch` always saves** the results of a tool run. It warns if a tool's `output` sets `save` to `false`, or sets `results_dir`, which `-o` replaces.
* **Validate first.** `flimbatch --dry-run` validates every run against the first rows of the files and runs nothing. `flimsettings tool --resolve FILE` and `flimsettings workflow --resolve FILE` show every setting of a run before you run it.
* **Strict columns.** A column that the settings name and the data doesn't have is an error. To use the closest matching column, as `--allow-guesses` did, use `--override processing.strict=false`, or set `"processing": {"strict": false}` in the tool or workflow file.
* **An unknown executor name for `-e`** is an error. In 0.6, `flimbatch` used the local executor.
* **Settings files must be complete.** `flimbatch` stops with an error if a settings file has invalid values, unknown settings or settings of tools that aren't installed. In 0.6 it ignored them.

Deprecated options still work and print a warning with the new form. They are removed in 0.8.0, except the executor names, which are removed in 1.0.0:

| 0.6 | 0.7 |
|---|---|
| `-c`, `--config FILE` | `-s`, `--settings FILE` |
| `--allow-guesses` | `--override processing.strict=false` |
| `-e LocalExecutor`, `LocalDaskExecutor`, `DaskExecutor` | `-e local`, `dask-local`, `dask` |
| `-a "num_workers=4"`, `--execargs` | `-e local:workers=4` |
| `flimanalyzer --batch ...` | `flimbatch ...` |

## Workflows in the GUI

Workflows defined in code, for example `Basic FLIRR Analysis`, are strict by default also in the GUI: a column that the settings name and the data doesn't have is an error. In 0.6 the GUI used the closest matching column. To use the closest matching column, clear the `Strict` check box next to `Load Settings...` and `Save Settings...` in the workflow's dialog (see [Validating the settings](/userguide/workflows.md#validating-the-settings)). `Save Settings...` saves it as `processing` > `strict`.

Workflow files are new in 0.7: a workflow as a JSON file of steps (see [Workflow files](/userguide/workflows.md#workflow-files)).

## Renamed tools

| 0.6 | 0.7 |
|---|---|
| `Autoencoder: Train` | `Autoencoder Train` |
| `Autoencoder: Run` | `Autoencoder Run` |
| `Autoencoder: Augment Data` | `Autoencoder Augment Data` |
| `Order Categories` | `Order Category Values` |

The former names still work in settings files, workflow files and `flimbatch --run`. Prefect tags the tasks also with the former autoencoder names, so concurrency limits set on the former names still apply. The results of `Order Category Values` are saved in a folder of the new name.

`Autoencoder Train` is now a workflow. Its step `Autoencoder Train Model`, which is in no menu, trains one model for each combination of settings.

## Results that change

Some bug fixes change results. Compare new results with results of 0.6 before you combine them. The changelog lists all changes under `Results that change`. The most important:

* **Autoencoder Train, weight decay:** in all earlier releases, the weight decay was always 0, and the `Weight decays` setting changed another value of the optimizer. Training now uses the weight decay as set. Trained models, reconstructions and the results of `FLIM Data Augmentation Tuning` change.
* **Autoencoder, missing values:** models trained with 0.7 scale the data before they set missing values to 0, as training does. Models saved before keep the earlier order, so their results don't change.
* **Autoencoder Augment Data, noise:** each feature gets its own noise level again, as in 0.5. Results with `Add noise` checked change.
* **Pivot without other category columns:** the result is now one row with the mean of each feature for each value. In 0.6 the result had a column `index` and columns named after the letters of the values.
* **Filter tool defaults:** the `Filter` tool started with the built-in defaults applies the three range filters that are on by default (`trp chi`, `NAD(P)H chi`, `FAD chi`). Uncheck them in the `Filter` dialog to keep all rows.
* **Import, `NADPH/NADH`:** the built-in `Import` workflow now adds this column; in 0.6 it was never added.
* **Concatenate, `Columns (side by side)`:** rows are now paired by position, not by row labels.

Other changes to the results:

* Plots are saved at 300 dpi by default; in 0.6 at 100 dpi. `Resolution (dpi)` in the tool's `Output` section sets another value.
* The default results folder is the folder FLIMAnalyzer was started from, or `-o`, instead of `FLIMAnalyzerResults` in the home folder.
* `Concatenate` names each row's table in the column `Input` instead of `Source`.
* `Merge` gives columns that both tables have the suffixes ` (left)` and ` (right)` instead of `_x` and `_y`. To get the names of 0.6, enter `_x` and `_y` as suffixes and clear `Combine identical columns`.
* Tools that add columns of fixed names, for example `PCA`, add `_1`, `_2` to a name that the table already has, instead of replacing that column.

## Names of saved files and folders

The names of saved result files and folders follow one rule:

* `%`, `τ`, `µ` and `μ` become `pcent`, `tau`, `u` and `u`.
* Letters lose their accents.
* Every other character than ASCII letters, digits, `-`, `_` and `.` becomes `_`.
* Repeated `_` become one, and `_`, `.` and spaces at the start and end are removed.

For example, the results of `Summary: NAD(P)H a2[%]` are saved as `Summary_NAD_P_H_a2_pcent`. In 0.6 only `%`, `:`, `/`, `\`, `|` and line breaks were replaced, so names kept spaces and brackets. Update scripts that find result files by name. The app setting `char_replacements` adds or changes replacements. A run whose inputs give the same folder name doesn't start.

## Plugin developers

These changes apply to tools written for FLIMAnalyzer, for example in a plugin (see [Programming Guide](/programming/index)).

* **Set `output_types`.** A tool without `output_types` can save every kind of result, with a `DeprecationWarning`. Set it, for example `output_types = (TableType,)`. It is necessary from 0.8.0.
* **Register a dialog.** A tool without a registered dialog is shown with the generic dialog, with a `DeprecationWarning`. Register one with `flim.gui.configdialog.register_dialog`, also for the generic `ConfigDialog`. From 0.8.0, a tool without a registered dialog is not shown in the menus and the tool panel.
* **Replace deprecated names.** They still work in 0.7, with a `DeprecationWarning`, and are removed in 0.8.0:

  | Deprecated | Use instead |
  |---|---|
  | `flim.core.parser` | `flim.core.categories.separate_by_patterns`, the presets of `Separate Categories` |
  | `flim.core.runner.default_max_workers` | `flim.core.runner.default_workers` |
  | `flim.batch` | `flim.core.batchrun` (run functions), `flim.batchcmd` (the `flimbatch` command) |
  | `flim.results.clean_path_component` | `flim.core.paths.path_name` |
  | `flim.core.tool.check_requirements` | `flim.core.tool.validate_requirements` |

* **Names changed without a deprecated name:** in `flim.core.settings`, `ToolEntry` is now `ToolSettings` (`autosave` and `results_dir` are in its `output`, a `ToolOutput`), the 0.6 `ToolSettings` map is `ToolSettingsMap`, and `tool_entry`, `read_tool_entry`, `write_tool_entry` are `tool_settings`, `read_tool_settings`, `write_tool_settings`. `flim.core.tools.check_executor_available` is now `flim.core.execution.ExecutionOptions.check_available`.
* **Removed without replacement:** `flim.core.importer`, `flim.core.preprocessor.defaultpreprocessor`, `ImportSettings`, `ParserSettings`, `PreprocessSettings`, `flim.batch.run_tool`, `import_table`, `filtered`, `IMPORTED`, `flim.core.tools.DASK_EXECUTORS`, `flim.core.filter.SeriesFilter` and `RangeFilter.apply_filter`.
* **Unique names.** The tool registry refuses a tool whose name, former name or short name equals that of another tool, with case ignored. The tool is not loaded, and the log says so.
