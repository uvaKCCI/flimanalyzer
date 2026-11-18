# Changelog

All notable changes to FLIMAnalyzer, newest first. It lists the changes that affect
users and plugin developers, not changes to the documentation. From 0.6.1 on, each
release has these sections where needed, in this order: `Results that change`,
`Changed`, `Added`, `Deprecated`, `Removed`, `Fixed`, `Security` and `Known issues`
(0.6.1 also has `Documentation`). The sections from `Changed` to `Security` are those of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The sections of 0.6.0 and
earlier are as published. Until 0.6.0, this file was called `CHANGES.md`.

## 0.7.0 - YYYY-MM-DD

Settings files, workflow files, the `flimsettings` command and new data tools, and bug
fixes for 0.6.2, several of which change results. New requirements: Python 3.12 to
3.14; PyTorch 2.14.1 for installs with uv from the source and the Docker CUDA image.
Users of 0.6: what to do when changing to 0.7 is on the user guide page "Moving from
0.6 to 0.7" (`docs/userguide/upgrading.md`, also at
https://flimanalyzer.readthedocs.io).

### Results that change

- **Calculated columns of 0.6 settings files:** until 0.6.2, `Import...` calculated its
  built-in columns and ignored the `preprocess` > `calculate` section of a settings
  file; `rename` and `drop` were applied. 0.7 converts the section into the settings of
  the `Calculate` tool, and the workflow that the GUI offers to save from a 0.6 file's
  import settings ends with a `Calculate` step that uses them. A file whose `calculate`
  section differs from the built-in one therefore gives other calculated columns than
  in 0.6.
- **Autoencoder Train, weight decay:** the `Weight decays` setting was passed to
  PyTorch's RMSprop optimizer as its smoothing constant (`alpha`), and the weight decay
  was always 0; in `FLIM Data Augmentation Tuning` the weight decay values varied
  `alpha` instead. This was so in every published release. Training now uses the
  weight decay as set, so trained models, reconstructions and tuning results change.
- **Autoencoder, missing values:** a model saved by `Autoencoder Train` set missing
  values to 0 before scaling the data, while training scaled first. `Autoencoder Run`
  and `Autoencoder Augment Data` therefore got other values than training for rows
  with missing values. Models trained now scale first; models saved before keep their
  order, so their results don't change.
- **Autoencoder Train without grouping:** rows that were exact duplicates of each
  other (all category and feature values equal) went into neither the training nor the
  validation set. They are now split like all other rows.
- **Autoencoder Augment Data, noise:** since 0.6.0, every feature got the same noise
  level, set by the features with the largest values (a change in pandas 2.0). Each
  feature gets its own noise level again, as in 0.5. Results with `Add noise` checked
  change.
- **FLIM Data Augmentation Tuning:** the KDE and Summarize steps grouped by the fixed
  column `Treatment` instead of the workflow's time-series column. Results are the same
  with the default (`Treatment`); they differ for other columns.
- **Concatenate, `Columns (side by side)`:** rows were paired by their row labels, not
  by position as its warning says, so tables whose rows were filtered or reordered got
  empty rows. Rows are now paired by position.
- **Bar Plot, `Drop missing`:** without grouping columns, the setting had no effect:
  each feature's mean left out only that feature's missing values. Now, as with
  grouping, checked (the default) leaves out the rows in which any plotted feature is
  missing, so all means and error bars come from the same rows.
- **Frequency Histogram, `barstacked` style:** without `Stacked` checked, each group's
  bars were in percent of that group's rows and were then stacked, so the stack added up
  to the number of groups times 100%. The `barstacked` style now always stacks: each
  group is in percent of all rows, and the stack shows the distribution of all rows.
- **Table windows opened while `Filter Data` is on:** the box was shown checked, but
  the range filters were not applied: the new window showed all rows, and tools started
  for it got all rows. The range filters now apply, so these tools get only the rows
  inside the ranges. The `<title> - Discarded` window opens with `Filter Features` and
  `Filter Categories` off.
- **`flimbatch` and the range filters:** `flimbatch` no longer filters the data by the
  table windows' range filters (`filters` > `use` in 0.6 settings files). To filter rows
  in a batch run, add a `Filter` step to a workflow file.
- **Filter tool defaults:** the `Filter` tool's range filters are now also the range
  filters that new table windows start with. Started with the built-in defaults, the
  `Filter` tool therefore applies the three range filters that are on by default (`trp
  chi` 0 to 4.7, `NAD(P)H chi` and `FAD chi` 0.7 to 4.7) to tables that have these
  columns; until 0.6.2 it started without filters. Uncheck them in the `Filter` dialog
  to keep all rows.
- **Import, `NADPH/NADH`:** the import calculated `NADPH/NADH` before `NADH %`, which it
  needs, so the column was never added. The built-in `Import` workflow now adds it.
- **Pivot without other category columns:** when the pivoted columns were the table's
  only category columns, the result had a column `index` and columns named after the
  letters of the values, one header line per letter (for example `c`, `t`, `r`, `l`
  for `ctrl`). The result is now one row with the mean of each feature for each value.

- **KS-Statistics, missing values:** a sample with missing values of the feature gave
  a missing p-value and statistic, `dissimilar` `No`, and the missing values were
  counted in `n`. Missing values are now left out of the test and of `n`.
- **KS-Statistics, grouping values:** with grouping columns, groups whose values are
  numbers or contain a backslash matched no rows and were left out of the results
  without a message; a value with a double quote stopped the tool with an error. Each
  group is now tested, so the results of such data get rows they didn't have.
- **Merge, missing key values:** rows with a missing value in a column merged on were
  paired with every row of the other table that also had a missing value there. These
  rows now match no row: `left`, `right` and `outer` keep them without the values of
  the other table, and `inner` leaves them out. A warning gives the number of these
  rows in each table.
- **Order Category Values:** values of a column that were not in the configured order
  became missing values, for example with a settings file used on other data. They
  now follow the configured values, in their order in the table, and the run summary
  names them.
### Changed

- **Closing a table window:** `Yes` to save now saves all rows, also those hidden by
  filters, as `Save All Rows...` and `File` > `Save All Windows...` do; until 0.6.2 it
  saved only the rows shown.
- **Split, Pivot and Summarize:** rows with a missing value in a grouping column (for
  Pivot also in the other category columns) are left out as before; the run summary
  now gives their number.
- **Reading data files:** `File` > `Open...` and `Import...` are replaced by
  `Open Tables...` and `Import Tables...` (see `Loading Data` in the user guide).
  `Open Tables` opens each file in a table window. `Import Tables` reads the files, one
  table per file, and runs a workflow file on them; the built-in `Import` workflow
  renames and drops the channels' columns, joins the tables and calculates the FLIM
  features, as `Import...` did with the default settings. Categories from the file names
  are now a `Separate Categories` step, whose presets are the filename parsers of 0.6
  (for example `FOV, Treatment, Cell`). The columns keep the files' order, after
  `Source`, `Directory` and `File`, and calculated columns are added at the end; until
  0.6.2 the columns were sorted alphabetically (text, then category, then the others).
- **Settings files of 0.6** are converted when read: the renamed, dropped and calculated
  columns (`preprocess`) become the settings of `Rename Columns`, `Drop Columns` and
  `Calculate`, the range filters become the `Filter` tool's filters, `working_dir`
  becomes `results_dir`, each tool's `autosave` and `results_dir` become its `output`
  section (`save`, `results_dir`, `formats`), a workflow's `strict` becomes its
  `processing` > `strict` (see `Workflows defined in code` below), and the autoencoder
  tools' `rescale` becomes `rescale_output`. The `import` section (delimiter, filename
  parser, patterns, files left out, column combinations) is not used any more: the GUI
  offers to save it as an equivalent workflow file, and `flimbatch` says that it is not
  used. In such a workflow file, combined categories are joined with `:` instead of
  `-`, for example `FOV:Treatment` = `FOV1:WT` instead of `FOV-Treatment` = `FOV1-WT`.
- **Filters of the table windows:** two switches in the side bar replace `Filter Data`:
  `Filter Features` switches the range filters, as `Filter Data` did, and `Filter
  Categories` the values hidden in category columns, which until 0.6.2 applied whether
  `Filter Data` was on or off. Hiding a value switches `Filter Categories` on, so the
  table shows the same rows as before. `Filter Settings...` is now `Filter Features...`
  and edits only the range filters; it has its own `Filter Features` checkbox, which
  replaces its `Use Filters` checkbox, and `Select All` and `Deselect All`. Each table
  window has its own range filters and switches. A change in one window doesn't change
  the others, and a new window starts with the defaults for new tables: the `Filter`
  tool's range filters and the `filters` setting. `Save as Preset...` > `Defaults for
  new tables` in `Filter Features` changes them. Until 0.6.2 all table windows shared
  one set of range filters. In settings files, `filters` > `use` becomes `filters` >
  `features` (`Filter Features`), beside `filters` > `categories`.
- **Settings file format:** app settings files and tool files saved by 0.7.0 have
  `schema_version` 2; workflow files, new in 0.7.0, have their own `schema_version` 1.
  FLIMAnalyzer 0.6 refuses them; 0.7.0 reads the files of 0.5 and 0.6.
- **Settings are saved automatically:** the GUI writes the settings you change (tool
  dialogs, presets, the range filters saved as the defaults for new tables, the default
  results folder) to the user settings file
  `usersettings.json` in the platform's settings folder, and uses them at the next
  start. Until 0.6.2 they were lost when the GUI closed unless exported.
  `flimbatch` does not read this file, so its results don't depend on settings changed
  in the GUI. `Import Settings...` applies a file to the session only. `Export
  Settings...` saves every setting as it is active, including the settings of every
  installed tool with its defaults.
- **Settings layers:** the settings come from these layers, from lowest to highest
  precedence: the built-in defaults, the user settings file (GUI only), the app
  settings file (`-s`), environment variables, command-line options. A higher layer
  changes each tool's section in `tools` and each tool's presets in `presets`
  separately, `max_windows` per kind of window, and `log` per setting; it
  replaces all other sections whole, for example `execution` and `filters`. For example, an app settings file with presets of `Filter` keeps
  the user's presets of `Calculate`. Exception: the user settings file's `favorites`
  take precedence over those of the app settings file.
- **Settings files are validated before use:** a file with unknown settings or invalid
  values, or a file that can't be used at all (it can't be read, comes from a newer
  version, or is a tool or workflow file), is not used. The GUI shows a message that
  lists the problems: at startup it then asks again which app settings file to start
  with, and `Import Settings...` and a tool dialog's `Load Settings...` load nothing.
  `flimsettings app --validate FILE` lists the problems of a file. `flimbatch` stops
  with an error if a settings file has invalid values, unknown settings or settings of
  tools that aren't installed; until 0.6.2 it ignored them, and used a tool's defaults
  when its settings were invalid, with only a line in the log. `run_summary.txt` names
  the settings files used.
- **`-s` takes app settings files only:** a tool file or a workflow file given with
  `-s` is an error: `flimbatch` runs it with `--run`, and the GUI loads a tool file in
  the tool's dialog. `flimbatch --run NAME` with an `-s` file that has no settings for
  the tool is an error; until 0.6.2 the tool ran with its defaults.
- **`flimbatch`** needs `--run`. It reads each file given with `-i` into a table of its
  own and runs each tool once per table (a tool with several inputs, such as
  `Concatenate`, once on all of them); until 0.6.2 it imported all files into one
  table, applied the import settings and the range filters, and saved `Imported.txt`.
  To get one imported table, use `--run Import`; to run a tool on it, use a workflow
  file that starts with the steps of `Import`. An unknown executor name for `-e` is now
  an error; until 0.6.2 `flimbatch` ran the local executor and only the log said so.
  With `-e dask-local`, one Dask cluster serves all runs of a call, instead of one
  cluster per run.
- **`flimbatch` results:** each call saves in one folder, `<output>/<date and time>/`,
  with a folder `run-<n>` for each `--run`, in the order given. Each `run-<n>` holds
  the run's `run_summary.txt` and `resolved.json` and a folder for each step,
  `<id>-<tool>`, for example `01-Summarize`, with a folder for each table and part
  below it where a step runs once per table or part. A tool given to `--run` runs as a
  workflow of one step, `01`. Workflows defined in code (`Basic FLIRR Analysis` and the
  autoencoder workflows) save the same way, also in the GUI: each of their steps has a
  fixed id and a folder `<id>-<tool>`, and a step run in a loop has a folder per part.
  Until 0.6.2 the results were saved in `<output>/<tool>/<date and time>/`, and those
  of a workflow defined in code were not in step folders. `flimbatch` always saves: it warns when a tool's
  `output` sets `results_dir`, which `-o` replaces, or `save` to `false`.
- **Default results folder:** the folder FLIMAnalyzer was started from, or `-o`, instead
  of `FLIMAnalyzerResults` in the home folder. A relative tool folder in a settings file
  (`output` > `results_dir`, for example `"results"`) now means a folder inside the
  default results folder.
- **Tool dialogs** have three sections, `Input`, `Settings` and `Output`; `Result
  prefix` is in `Output`. `Save results in` is now `Save results`, with `Use the default
  folder`, `Make Default Folder` and the formats below it. A tool that follows the
  default folder stores no folder of its own; the formats offered are those of the kinds
  of result the tool makes. The dialogs offer only the columns the selected table has,
  show warnings for some tools, and hide settings that have no effect (`Grouping` in
  `Series Analysis`, `Random Forest` and `Heatmap`; `Random seed` in `PCA`; for
  `Concatenate`, the settings of the other direction). The dialogs of `Pivot`,
  `Unpivot`, `Categorize Data`, `Scale` and the new data tools show an example table:
  a few rows of the selected table, the input columns next to the columns the tool
  makes. `Save Settings...` saves a new file as a tool file (see `Added`); its file
  dialog starts in the workflow folder, and before it saves a new file into a folder of
  the app settings search path, it asks first (`Use Workflow Folder`, `Save Here`).
- **Saved results:** plots saved by a tool (`Save results`, workflows, `flimbatch`) are
  `.png` files at 300 dpi by default; `Resolution (dpi)` in the tool's `Output` section
  sets another value. Until 0.6.2 they were saved at 100 dpi, matplotlib's default
  resolution, so the same plot now has three times as many pixels in width and height.
  Tables are tab-separated `.txt` by default, as in 0.6.2. A run folder started in the
  same second as another one gets `-2`, `-3` added.
- **Quitting** with unsaved windows asks `Cancel`, `Review...`, `Save All Windows...` or
  `Discard All`, also when you log out or shut down the computer (where the system lets
  it ask). Plot windows count as unsaved after edits, such as an axis, a label or a
  line; until 0.6.2 they were not checked.
- **Table window:** the buttons `Save All` and `Save View` are now `Save All Rows...` and
  `Save Shown Rows...`. `Pivot...` and `Unpivot...` open the `Pivot` and `Unpivot`
  dialogs for the window's table; the window's own two-step pivot is removed, and its
  result is `Table: Pivoted`. A new range filter has no limits; until 0.6.2 it was 0 to
  100.
- **Concatenate:** the column that names each row's table is `Input` instead of
  `Source` (`Source` now holds each row's file), and `Add Input column` can leave it out.
  A single table is passed on unchanged. A table saved by 0.6 with a `Source` column of
  table names opens with it renamed `Source (before Read)`.
- **Merge:** columns that both tables have and that aren't merged on get the suffixes
  ` (left)` and ` (right)` instead of `_x` and `_y`; with `Combine identical columns`
  (checked by default), such a column whose values agree in both tables becomes one
  column. Enter `_x` and `_y` as suffixes and uncheck `Combine identical columns` to
  name them as 0.6 did.
- **New column names:** tools that add columns of fixed names (PCA, Gaussian Mixed
  Model, Unpivot, the autoencoder tools) add `_1`, `_2` to a name the table already has,
  instead of replacing that column. `K-Means` and `Categorize Data` warn when they
  replace a column of the chosen name.
- **Order Categories** is now `Order Category Values`: it orders the values within
  category columns. Its results are saved in a folder of the new name. The former name
  still works in settings files, workflow files and `flimbatch --run`, with a warning
  (deprecated).
- **Autoencoder tools** are named without a colon: `Autoencoder Train`, `Autoencoder
  Run` and `Autoencoder Augment Data`. `Autoencoder Train` is now a workflow: the step
  `Autoencoder Train Model`, which is in no menu, trains one model for each combination
  of settings, and `Collect Files` lists the model files of all combinations in one
  table. The former names still work in settings files, workflow files and
  `flimbatch --run`, with a warning (deprecated), and the tasks are also tagged with
  them in Prefect, so concurrency limits set on the former names still apply.
- **Workflows defined in code** (for example `Basic FLIRR Analysis`) are strict by
  default also in the GUI: a column that the settings name and the data doesn't have
  is an error. Until 0.6.2 the GUI used the closest matching column, unless `Strict`
  was on. The check box `Strict`, next to `Load Settings...` and `Save Settings...`,
  replaces the `Strict` setting; it is saved as the tool's `processing` > `strict`. A
  saved `strict` of 0.6 moves there when the file is read; `null` (automatic) becomes
  strict.
- **File and folder names** of saved results follow one rule: `%`, `τ` and `µ` become
  `pcent`, `tau` and `u`, letters lose their accents, and every other character than
  ASCII letters, digits, `-`, `_` and `.` becomes `_`. For example, the results of
  `Summary: NAD(P)H a2[%]` are saved as `Summary_NAD_P_H_a2_pcent`. Until 0.6.2 only
  `%`, `:`, `/`, `\`, `|` and line breaks were replaced, so names kept spaces and
  brackets. `char_replacements` in the `output` section of tool settings, tool files and
  workflow files (workflow and step) adds or changes replacements; `resolved.json`
  states each step's. A
  run whose inputs give the same folder name doesn't start.
- **`run_summary.txt`** also lists the versions of FLIMAnalyzer, Python, the installed
  dependencies of FLIMAnalyzer and the packages of installed plugin tools (with a Dask
  executor also `dask` and `distributed`) under `Versions`, and how the tasks ran under
  `Execution`, so a results folder records them also without the Prefect UI, and
  the time the run took under `Elapsed`. Its task table names each task's step
  (`Step`) and results folder in the run (`Folder`). Above it, `Inputs` lists each
  input of the run once, with the steps it enters: a file with its path, size, format,
  SHA-256 and modification time, or a table or image with its class, shape, data
  types, a SHA-256 of its content and a description (columns by role, missing values;
  in the GUI also the table window it came from and the filters that change the rows
  a tool gets).
- **Heatmap:** the title is `Correlation`; until 0.6.2 it was `Data grouped by ...`,
  although the correlations are those of the whole table.
- **Log files:** each GUI session writes its own log file in the platform's log folder,
  for example `flimanalyzer_2026-11-09T14-23-43_12345.log`, never overwritten. A log
  file that reaches 10 MB continues in a new file; three older parts are kept. At
  startup the GUI removes its log files older than the app setting `log` >
  `max_age_days` (default 30 days). Each
  `flimbatch` call writes `flimbatch.log` in its results folder, or, with a log folder
  set (`--log-dir`, `FLIM_LOG_DIR`), a file named after the call's start in that folder.
  Until 0.6.2 the GUI wrote `flimanalyzer.log` in the start folder, replaced at each
  start, and `flimbatch` wrote no file. Log lines name the module that wrote them, and
  errors in the GUI are written to the log. `flimbatch` shows log lines in the terminal
  with the time, as the GUI's terminal does, for example
  `08:29:03.614 | INFO    | flim.core.batchrun - ...`; until 0.6.2 they were
  `INFO message`.
- **Requirements:** Python 3.12, 3.13 and 3.14. Installs with uv from the source and
  the Docker CUDA image use PyTorch 2.14.1 with CUDA 13.0 (until 0.6.2: 2.11.0 with
  CUDA 12.8 on Windows and Linux x86_64), which needs NVIDIA driver 580 or newer and a
  GPU of the Turing generation or newer. For older GPUs, such as the V100, see
  `PyTorch and the GPU` in the installation guide. New dependencies: `filelock`,
  `platformdirs`, `pydantic-settings`.
- **Version of development installs** (from the repository, between releases): it names
  the next minor release as a development release, for example `0.7.0.dev12+g1a2b3c4`;
  until 0.6.2 it named the last release, for example `0.6.1.post12+g1a2b3c4`. Release
  versions are unchanged.
- **Plugin and tool API** (developers): names that changed without a deprecated alias,
  because an alias would behave differently: in `flim.core.settings`, `ToolEntry` is now
  `ToolSettings` (`autosave` and `results_dir` are in its `output`, a `ToolOutput`),
  the 0.6 `ToolSettings` map is `ToolSettingsMap`, and `tool_entry`, `read_tool_entry`,
  `write_tool_entry` are `tool_settings`, `read_tool_settings`, `write_tool_settings`.
  `flim.core.tools.check_executor_available` is now
  `flim.core.execution.ExecutionOptions.validate_available`. The tool registry refuses a
  tool whose name, former name or short name equals another tool's, ignoring case (the
  tool is not loaded, and the log says so). See the
  Programming Guide for how API changes are handled.

### Added

- **App settings files:** `-s NAME` finds a settings file by name in the app settings
  search path (`FLIM_APP_SETTINGS_PATH`, `appsettings_path`, or the folder
  `appsettings` in the platform's settings folder). Started without `-s`, the GUI asks
  which file to start with, if there are any, and can keep one as the default. The list
  shows only app settings files, not the tool and workflow files in the same folders;
  `Browse...` adds a file from another folder and offers to add that folder to the
  search path. `Export Settings...` offers to add the file's folder to the search path,
  and asks for an optional `description` of the file, which the list of files at
  startup shows.
- **`File` > `Settings...`** (on macOS: `FLIMAnalyzer` > `Settings...`) shows the app settings of the session (results folder,
  executor, Prefect server, server timeout, log folder), where each value comes from,
  and how to change it.
- **Command line and environment:** both programs take `-s`, `-o`,
  `-e NAME[:KEY=VALUE,...]` (`local`, `dask-local`, `dask`),
  `--prefect-server`/`--no-prefect-server`, `--server-timeout`, `--log-dir`,
  `-l`/`--log-level` (also `--log`, as until 0.6.2), `-i`, `-x`,
  `-r`/`--run` and `-w`/`--workflow-path`. `-i`, `-x` and `-w` take several values and
  can be repeated. `--run` also takes a workflow file (a path, or a file name ending in
  `.json` in the workflow search path or among the built-in workflow files); repeated, the runs are done in the order given.
  `flimbatch` also takes `--dry-run` and `--override`. Both programs read the
  environment variables `FLIM_EXECUTION`, `FLIM_PREFECT_SERVER`,
  `FLIM_SERVER_TIMEOUT`, `FLIM_LOG_DIR`, `FLIM_LOG_LEVEL`, `FLIM_APP_SETTINGS_PATH`
  and `FLIM_WORKFLOW_PATH`; the GUI also reads `FLIM_RESULTS_DIR` and
  `FLIM_USER_SETTINGS`, and `flimbatch` also reads `FLIM_DRY_RUN`. The app setting `server_timeout` (default 60 s) sets how
  long FLIMAnalyzer waits for the Prefect server, also for a local one that it starts,
  and for a Dask cluster.
- **`flimbatch --dry-run`** reads the first rows of the files, validates the output
  folder, the executor, the Prefect server and every run against them, and runs
  nothing. It needs `-o`, and writes its log there, or in the log folder if one is set.
  The first and the last line of its output say that it is a dry run and what made it
  one (`--dry-run` or `FLIM_DRY_RUN`).
- **`flimbatch --override GROUP.FIELD=VALUE`** (repeatable) sets a field of the
  `output` or `processing` group for every step of every run, for example
  `output.save=true`, `output.formats=table:csv,plot:svg` or `processing.strict=false`.
  A prefix limits an override to one run (`run-2.`) or one step (`run-2.steps.3.`, or
  `steps.3.` with a single `--run`). The order of precedence is: `--override` of the
  step, of the run, of every run; then the step in the file, the workflow, the tool's
  default. The tools' `config` can't be set this way. A workflow defined in code always
  saves its results: `output.save=false` for its run is an error. The run summary lists
  the overrides, and
  `resolved.json` holds the overridden settings.
- **`resolved.json`:** `flimbatch` writes the settings of each run into
  `run-<n>/resolved.json`, as a workflow file (for a workflow defined in code, a tool
  file) that states every setting of every step and the formats of each kind of
  result. Settings that depend on the data (`features: all`, guessed columns, skipped
  entries) stay as given and are resolved for each table. `flimbatch --run
  resolved.json` on the same files with the same FLIMAnalyzer version repeats the
  run. `run_summary.txt` lists, for each table, the columns guessed and the entries
  skipped, and records the versions and the settings files. Runs in the GUI that save
  their results write `resolved.json` into their results folder too.
- **`flimsettings`:** a command that lists, shows, validates, resolves and updates
  settings without the GUI. `flimsettings tool` and `flimsettings workflow` take
  `--list`, `--show FILE|NAME`, `--validate FILE` and `--resolve FILE` (the file with
  every setting stated, as `flimbatch` runs it, also with `--override`), and `tool` also
  `--update FILE`; `-w` sets the workflow search path. `--show NAME` prints the default
  settings of a tool, or of a workflow defined in code, as a tool file; a workflow file
  is found by its file name or by its `name`, as with `flimbatch --run`.
  `flimsettings app` takes `--list` (the app settings files in the search path),
  `--show` (the app settings of `flimanalyzer` and `flimbatch`, and where each value
  comes from; with `-s`, of an app settings file), `--validate FILE` and
  `--update FILE`. `flimsettings user --show` shows
  the user settings file, and `flimsettings env` (`--list`, `--show`) the `FLIM_*`
  environment variables. The exit code is 1 if a validation finds a problem.
- **Tool files:** a tool dialog's `Save Settings...` saves a new file as a tool file:
  the tool's name with its `config`, `output` (`save`, `formats`) and `processing`, in
  the form of a workflow step, without the results folder. `Load Settings...` reads it,
  and `flimbatch --run FILE` runs it as a workflow of one step; a tool file of a
  workflow defined in code runs that workflow with the file's settings, and a tool file
  of `Import Tables` reads the files with its read settings and runs its workflow.
- **Settings files of older versions** can be updated: when the GUI uses a settings file
  of an older version (at startup, with `Import Settings...` or with a tool dialog's
  `Load Settings...`), it asks whether to update it. `Update` rewrites the file in the
  current format and keeps the original next to it as `<name>.v<n>.json`, for example
  `lab.v1.json`, which the older version can still read; `Not Now` uses the file as it
  is and asks again the next time. `flimsettings app --update FILE` and
  `flimsettings tool --update FILE` do the same. `flimbatch` never changes a settings
  file. Before the GUI writes the user settings file in a new format for the first
  time, it keeps the old file as `usersettings.v<n>.json`.
- **Workflow files:** a workflow as a JSON file of steps, each a tool with its own
  `config`, `output` (`save`, `formats`) and `processing`. The steps run once per
  table until a step such as `Concatenate` joins the tables. A step whose tool makes
  its results in parts, for example `Summarize` with a table per feature, passes each
  part on, and the later steps run once per part. Only the results of steps with
  `output` > `save` are saved: a workflow in which no step saves is refused, and a step
  that doesn't save and whose results no later step uses gets a warning. A step's
  formats take precedence over the workflow's `output` > `formats`, for each kind of
  result. `processing`, for the whole workflow or per step, sets per field whether a
  column that the data doesn't have is an error or is replaced by the closest one
  (`strict`, default `true`), which entries a step may skip if they don't apply to the
  data (`skippable`: `none`, `some` or `all`), and which entries must apply although
  skippable (`required`). `category` places a workflow in the menus (default:
  `Workflow`); `Import Tables...` offers those of `["File", "Import"]`. Workflow files
  are found in the workflow search path: the folders of `-w`, else of
  `FLIM_WORKFLOW_PATH`, else of `workflow_paths` in the user settings file, else the
  folder `workflows` in the platform's settings folder. They run with
  `Import Tables...`, their menu entries, `Workflow` > `Run Workflow File...` (on the
  current table), or `flimbatch --run`. The built-in `Import` workflow is one. In the
  GUI, a run of `Import Tables` or of a workflow file that would open more windows than
  the app setting `max_windows` allows (default: 10 tables, 10 plots, 4 images)
  doesn't start.
- **`Source` column:** each table read from a file gets `Source`, the file as a URI,
  for example `file:///data/Results-a-Dox15_01.txt`. `Data` > `Directory/File to Source`
  adds it to tables imported with 0.6 or earlier.
- **New tools:** `Rename Columns` (#10), `Drop Columns`, `Fuse Categories` and
  `Separate Categories` (modes `delimiter`, `pattern`, `template`; presets) in `Data`;
  `Calculate` (expressions and functions, presets) and `Scale` (standardize, min-max or
  robust, per group) in `Analysis`; `Collect Files`, for workflow files and `flimbatch`
  only, which lists the files of its inputs in one table.
- **Filter tool:** filters by category values, ranges and conditions written as
  expressions, and, in settings files, groups (`all`, `any`, `not`). The filters are in
  three parts, each with its own switch: range filters (`features`, `Use range
  filters`), category filters (`categories`, `Use category filters`) and other filters
  (`other`, `Use other filters`). `Use filters` (`enabled`) switches all filters; off,
  the tool keeps all rows. A filter applies only if `Use filters`, the switch of its
  part, the `enabled` of each group that contains it and its own `enabled` are all on.
- **Presets:** `Load Preset...`, `Save as Preset...` and `Remove Presets...` in the
  `Calculate`, `Separate Categories` and `Filter` dialogs and in a table window's
  `Filter Features`. Presets are saved in the user settings file, in the `presets`
  section by tool name. A preset of `Filter Features` holds the table window's range
  filters and `Filter Features` as the `Filter` tool's range filters, and
  `Filter Features` also loads them from and saves them to settings files, as the
  `Filter` dialog's `Load Settings...` and `Save Settings...` do, and saves the range
  filters as the defaults for new tables.
- **Standardize input** in `PCA`, `K-Means` and `Gaussian Mixed Model`: one setting with
  the same meaning in all three. The defaults keep the earlier behaviour (on, on, off).
- **Autoencoder Augment Data:** `Random seed`, for the same noise on every run.
- **Random Forest:** the accuracy on the test data as a table, `Table: Accuracy Data`;
  until 0.6.2 it was shown only in the importance plot.
- **Unpivot** of columns with fewer header lines than the others, for example after
  `Scale` with `Keep original`: their rows get `Label for a missing line` (default
  `none`). Until 0.6.2 this was an error.
- **Save formats:** tables as `tsv` or `csv`, plots as `png` (with `Resolution (dpi)`),
  `svg` or `pdf`, chosen in a tool's `Output` section, in `Save All Windows...` and in
  the save dialogs of table and plot windows, which warn when a format would change the
  headers.
- **`File` > `Save All Windows...`** saves all open tables and plots in a new dated
  folder (#14).
- **`File` > `Favorites...`** chooses the tools and workflows the tool panel shows, and
  their order.
- **Prefect UI:** the new `Monitor` menu, also a group of the tool panel: `Prefect
  Server` opens the Prefect UI in the web browser, and `Last Run` opens the page of the
  last run the GUI started, also in an earlier session. Each task's settings are shown
  in the task run's `Artifacts` tab. Each flow run's `Artifacts` tab shows the versions
  of FLIMAnalyzer, Python and the packages listed in `run_summary.txt` (see
  `Changed`), how the tasks ran (threads or Dask, with their settings) and the input
  files. FLIMAnalyzer's log messages from a run are shown in the run's `Logs` tab,
  except those of tasks that Dask runs in other processes.
- **Icons** at 64 px for high-resolution screens; icons for the new tools.
- **Plugin and tool API** (developers): `Tool.short_name`, `Tool.example` (a table or
  one line), `Tool.validate_data`, `Tool.proposals` and `Tool.inapplicable_fields` for
  the dialogs; `Tool.category` as a list of a menu and its submenus, and `None` or `[]`
  for no menu; `flim.gui.configdialog.register_dialog`; `Tool.output_types`;
  `Tool.mappable_output` and `Tool.output_prefix` for results in parts;
  `Tool.skippable_fields` and `Tool.never_guessed` for `processing`; `Tool.extra_tags`;
  tool lookups accept `former_names`; each data type declares its `save_options` and
  writes with `DataType.save`; `DataType.content_hash` and `DataType.describe`, which
  identify and list a value among a run's inputs (None and the class by default, so
  data types of plugins can add their own); a tool call's `step`, which names its
  results folder; `flim.core.paths.path_name`; `flim.__version__`.

### Deprecated

Deprecated names keep working for at least one minor release; the Programming Guide
describes how API changes are handled.

- **`-c` / `--config`:** use `-s` / `--settings`. Removed in 0.8.0.
- **Executor names `LocalExecutor`, `LocalDaskExecutor`, `DaskExecutor`:** use `-e local`,
  `-e dask-local` and `-e dask`. Removed in 1.0.0.
- **Former tool names** (`Autoencoder: Train`, `Autoencoder: Run`, `Autoencoder: Augment
  Data`, `Order Categories`, `Concat Data`) in settings files, workflow files, tool
  files and `--run`: use the current names (`Autoencoder Train`, `Autoencoder Run`,
  `Autoencoder Augment Data`, `Order Category Values`, `Concatenate`). A former name
  gives a warning naming the current one. `flimsettings app --update`, `flimsettings
  tool --update` and the GUI's `Update` save settings files under the current names.
  Removed in 0.8.0, and so are the Prefect tags of the former names: set concurrency
  limits on the current names.
- **`-a` / `--execargs`:** put the options after the executor name, as
  `-e NAME:KEY=VALUE,...`; `num_workers` is now `workers`. Removed in 0.8.0.
- **`--allow-guesses`** (`flimbatch`): use `--override processing.strict=false`. Removed
  in 0.8.0.
- **`flimanalyzer --batch`:** use `flimbatch` with the same arguments. Removed in 0.8.0.
- **`flimbatch --run NAME` with the tool's settings from the `-s` file:** save the
  tool's settings as a tool file (`Save Settings...` in the tool's dialog) and run it
  with `--run FILE`. Removed in 0.8.0.
- **`Directory` and `File` columns:** still added when a file is read; `Source` replaces
  them. Removed in 0.8.0. To add `Source` to older tables, use
  `Directory/File to Source`.
- **`defaults.json` in the start folder:** the GUI started without `-s` still uses it,
  with a warning. Move it to a folder of the app settings search path, give it a name,
  for example `cells.json`, and start with `-s cells`. Removed in 0.8.0.
- **`flim.core.parser`** (developers): the filename parser classes of 0.6. Importing the
  module issues a `DeprecationWarning`; use Separate Categories
  (`flim.core.categories.separate_by_patterns`, the `presets` of `Separate Categories`). Removed in
  0.8.0.
- **`flim.core.runner.default_max_workers`** (developers): use `default_workers`. Removed
  in 0.8.0.
- **`flim.batch`** (developers): use `flim.core.batchrun` for the run functions and
  `flim.batchcmd` for the `flimbatch` command. Importing the module issues a
  `DeprecationWarning`. Removed in 0.8.0.
- **`flim.results.clean_path_component`** (developers): use `flim.core.paths.path_name`.
  Removed in 0.8.0.
- **`flim.core.execution.ExecutionOptions.check_available`** (developers): use
  `validate_available`; the former name issues a `DeprecationWarning`. Removed in 0.8.0.
- **`flim.core.tool.check_requirements`** (developers): use
  `flim.core.tool.validate_requirements`; the former name issues a `DeprecationWarning`.
  Removed in 0.8.0.
- **Plugin tools without `output_types`** (developers): such a tool can save every kind
  of result, with a `DeprecationWarning`; set `output_types`, for example
  `(TableType,)`. Required from 0.8.0.
- **Plugin tools without a registered dialog** (developers): still shown in the menus
  and the tool panel with the generic dialog, with a `DeprecationWarning`; register one
  with `flim.gui.configdialog.register_dialog`, also for the generic `ConfigDialog`.
  Not shown from 0.8.0.

### Removed

- **The 0.6 importer:** the `Import` dialog with its delimiter, filename parser, patterns,
  files left out and `Column Combos`, and the `import` section of the settings. What is
  done with data files is now a workflow file's (see `Changed`). `flimbatch` no longer
  writes `Imported.txt`.
- **Filter Settings' `Load` button**, which did nothing.
- **Plugin and tool API** (developers), without replacement in the API: `flim.core.importer`,
  `flim.core.preprocessor.defaultpreprocessor`, `ImportSettings`, `ParserSettings` and
  `PreprocessSettings` (import is a workflow); `flim.batch.run_tool`, `import_table`,
  `filtered` and `IMPORTED` (internals of `flimbatch`);
  `flim.core.tools.DASK_EXECUTORS`; `flim.core.calculator` (an empty module); `flim.core.filter.SeriesFilter` (could not be
  created) and `RangeFilter.apply_filter`.
- **Dependency** `importlib-resources`: the standard library's `importlib.resources` is
  used.

### Fixed

- **Save dialogs on macOS:** with wxPython 4.2.5, a save dialog that offered one file
  type failed with the error `C++ assertion "nIndex < m_nCount" failed` when `Save` was
  clicked, and no file was written. This affected `Export Settings...`, the tool
  dialogs' `Save Settings...` and `Save Feature Settings...`, and in 0.6.2 also saving
  tables and plots. These dialogs now also offer `All files`, and the dialogs that
  save JSON files add `.json` to a file name without it.
- **Prefect server:** the instance that started the local Prefect server stopped it when
  it quit, and every run of other open instances (GUI or `flimbatch`) then failed with
  `ConnectError: Connection refused`. Each run now checks the server first and finds or
  starts one again if it is gone.
- **CPU training on CUDA builds of PyTorch:** with the CPU selected, PyTorch's optimizer
  still checked for a GPU, which could initialise CUDA and print the warning of #143
  (#217).
- **Opening a file with the name of an open window** (`data.txt` from another folder)
  replaced that window's table and cleared its unsaved changes, without asking. It now
  opens in a new window.
- **Window menu on macOS** listed every window twice.
- **Text fields in dialogs** dropped spaces and tabs at the start and end of values.
- **Filter Settings (now `Filter Features`):** `Dropped from view` and the remaining count ignored the rows
  hidden by a single other filter.
- **Merge without shared category columns:** with automatic `Merge on`, two tables
  without a shared category column stopped the run with an `IndexError`. The dialog
  and the validation of workflow files now show the error, and the tool doesn't run.
- **Filter Settings (now `Filter Features`) checkboxes:** the checkbox of the first row, and of the row
  clicked last, couldn't be checked or unchecked; a click on it opened the cell editor
  instead.
- **Messages not shown:** `OK` with nothing selected, an invalid pattern in Pattern
  Rename, and a replacement that is not valid (for example `\1` without a group) did
  nothing instead of showing an error.
- **Plot axis dialog:** `Min value` and `Max value` were rounded to 2 decimals, so
  changing only the label of an axis with small limits (for example 0.0012 to 0.0048)
  set both limits to 0. The fields now show all digits, and a limit that is not changed
  stays the same.
- **Autosize Cols** failed in a table with missing text values or with no rows, and the
  column widths stayed as they were.
- **Saving settings files:** `Export Settings...` and `Save Settings...` wrote the file
  in place, so a failure while writing (for example a full disk) left an incomplete
  file. The file is now written to a temporary file in the same folder that then
  replaces it; if writing fails, the file is left unchanged.
- **Saving a table window when closing it** suggested the file name `frame.txt`; it now
  suggests the window's title.
- **Save Feature Settings...:** an error writing the file, for example to a folder that
  doesn't exist, was not shown; it is now shown below the table.
- **Frequency Histogram, stacked, `Binned data table`:** each group's column held the
  height of the stack up to that group, not the group's own values.
- **KDE plot colors:** with two grouping columns whose second had more than 4 values, or
  with more than 10 groups, colors repeated, so curves of different groups looked the
  same. The color now always shows the 1st grouping column, and shades of it show the
  values of the 2nd; above 10 groups, the colors don't repeat.
- **Swarm Plot:** its note advised a strip plot, which FLIMAnalyzer doesn't have.
- **`flimbatch --run "Concat Data"`** failed: tools are now found by their former names
  too.
- **Import with a rename of empty text** inserted the new name between all characters
  of the column names; `Rename Columns` skips a replacement with empty text.
- **Docker:** matplotlib warned at every start that it can't write its cache folder; the
  images set `MPLCONFIGDIR` to `/tmp/matplotlib`.
- **`-i` and `-x` given more than once** (`-i a.txt -i b.txt`) used only the files of
  the last use. All uses now count, in both programs.
- **`flimbatch` plots on macOS:** tools that draw plots failed, because macOS' default
  matplotlib backend can't draw outside the main thread. `flimbatch` now draws with
  the `Agg` backend, which opens no windows.
- **Table window:** the window could be lower than its side bar, so the last buttons
  were cut off. It now opens at least as high as the side bar, within the screen, and
  can't be made lower.
- **Series Analysis settings** listed the statistics in a different order each time
  they were saved, so saved files changed without a change of settings. They are now
  saved in a fixed order.
- **Import Settings and Export Settings** changed the working folder to the folder of
  the chosen file. They no longer do. `Export Settings...` opens at the first folder of
  the app settings search path.
- **App settings files** with a format of a kind that a tool doesn't make in the
  tool's section, for example a plot format for `Summarize`, were accepted. The tool's
  section is now reported as invalid and not used, as in tool and workflow files.

### Known issues

- **Windows:** the autosave fix of 0.6.0 for mapped network drives (#163) is not yet
  verified on Windows. Please report in the issue.

## 0.6.2 - 2026-11-07

Bug fixes for 0.6.1, and the CPU Docker image. Same requirements as 0.6.1.

### Results that change

- **Concatenate, `Columns (side by side)`, after `Order Categories`:** tables side by side
  are lined up by their row numbers. `Order Categories` now numbers the rows in their new
  order (#119), so its result is paired with the other table by position; until 0.6.1 its
  rows kept their old numbers and were paired with the rows they came from.

### Changed

- **Saved tables** (`Save results in`, workflows, `flimbatch`) are tab-separated, without
  the row numbers, like tables saved from a table window (#119). Until 0.6.1 they were
  comma-separated, with the row numbers as an unnamed first column, which after sorting
  (e.g. `Order Categories`) were out of order. Scripts that read saved results need to
  read them as tab-separated, without an index column; FLIMAnalyzer reads both.
- **Tools need the features they work on** (#204). Most tools need at least one feature
  selected, `PCA`, `Scatter Plot`, `Series Analysis`, `Autoencoder: Train` and
  `FLIM Data Augmentation Tuning` two, and some a grouping column (e.g. `FLIRR Plot`);
  `Summarize` needs at least one statistic. The dialog marks the field and keeps `OK`
  disabled until they are selected; `flimbatch` and workflows stop with an error
  naming the tool. Most tools' defaults select no features, so a `flimbatch` settings
  file must select them.

### Added

- **Warnings from tools:** a tool can report a warning while it runs; the task stays
  completed, and the warning is its message in the run summary, the log and the Prefect
  UI. The GUI shows warnings after a run. First use: `Concatenate` side by side warns
  when the tables' rows don't match by their shared category columns or row counts,
  and points to `Merge`, which pairs rows by category values (#210).

### Fixed

- **Concatenate** side by side with `Numeric columns only` gave two columns of the same
  name when both tables had it, and later tools failed; a taken name now gets the
  table's name, e.g. `x (Table: B)`, as without the option (#211).
- **Too few features:** with no features selected, most tools ran and produced nothing,
  and `Gaussian Mixed Model`, `K-Means` and `PCA` failed with unclear errors; `Summarize`
  with no statistics failed with `KeyError: "None of [...] are in the columns"` (#204).
  FLIMAnalyzer 0.5 checked this before a run; 0.6.0 lost the check.
- **Quitting** with unsaved table windows now asks first (Quit / Cancel); until 0.6.1
  their results were lost without asking, also in 0.5 (#207).
- **Order Categories** numbers the rows in their new order (#119).
- **Docker:** the CPU image (`0.6.2-cpu`, `latest-cpu`) is published again; for 0.6.1 its
  version label read `0.6.1-cpu`, and the check before publishing stopped it (#200).

### Known issues

- **Windows:** the autosave fix of 0.6.0 for mapped network drives (#163) is not yet
  verified on Windows. Please report in the issue.
- **Quitting:** plot windows are not checked for unsaved changes yet; a full dialog
  (Review, Save All, Discard All) and tracking of later edits are planned for 0.7.0.

## 0.6.1 - 2026-11-06

Bug fixes for 0.6.0, corrected and completed documentation, and fixes of the Docker
images. Same requirements as 0.6.0.

### Results that change

- **Relative Change:** rows became empty when a category column that is not under
  `Grouping` (e.g. `Cell`) has values that differ between the reference rows and the
  other rows (#178). Rows are now matched on the grouping columns only. Where 0.6.0 gave
  a value, it is unchanged; the log names groups that have no reference rows.
- **FLIM Feature Analysis:** the KDE, Summarize, bar plot and KS steps used the fixed
  columns `Treatment`, `FOV` and `Cell` instead of the `Time series` and `Grouping`
  settings (#190). Results are the same with the defaults (`Time series` `Treatment`,
  `Grouping` `Treatment`, `FOV`, `Cell`); they differ for other columns.
- **Histogram** with `Density` checked: the axis and the table said percent
  (`relative counts [%]`, `[rel %]`), but the values are a density (area 1). They now
  say `density` (#181). The values are unchanged; only the labels are corrected.

### Changed

- **Prefect server at startup:** if port 4200 is taken, FLIMAnalyzer starts its local
  Prefect server on a free port. If no server can be started, it stops with an error
  (a message box in the GUI) instead of falling back to Prefect's temporary servers
  (#195). With `--no-prefect-server`, Prefect still starts a temporary server for each
  run.
- **Help → Documentation** opens the documentation of the installed version, instead of
  the latest.

### Fixed

- **Prefect server in the GUI:** tools and workflows started in the GUI didn't use the
  Prefect server FLIMAnalyzer found or started at startup (#195). Without a server in
  the Prefect profile, each run started its own temporary server; with a server in the
  profile that didn't answer or rejected the API key, runs failed. They now all use the
  server chosen at startup. `flimbatch` was not affected.
- **Concatenate**, `Columns (side by side)` with `Numeric columns only` off, failed
  with `KeyError: 'Old Index'` (#176). Columns of the second table whose name is
  already taken get the table's name, e.g. `Treatment (B)`.
- **Autoencoder:** Run and Augment Data failed with `All features` checked (#177).
- **Autoencoder: Train:** the loss plot legend said "testing" for the validation loss
  (#179).
- **Plot window:** `Cancel` in the line colour dialog still changed the colour (#188).
- **Workflow dialogs** showed a `Result prefix` that no workflow used; it is no longer
  shown (#189).
- **Docker images:** the version inside the image read `0.6.0+d20261103` instead of
  `0.6.0` (#174). The images now carry the standard OCI metadata (version, commit,
  base image), and CI checks the version, commit and `flimbatch --help` before it
  publishes an image. The base image is pinned and kept current.

### Documentation

- The user guide was checked against the code and corrected throughout: the controls
  common to all dialogs, the analysis pages (full pages for the autoencoder tools), the
  plot pages (`Single figure`, `Legend`) (#173) and the plot window, the data pages,
  workflows, batch mode, settings and menus. All screenshots are from 0.6.1.
- The 0.6.0 release notes said Basic FLIRR Analysis divides by "the mean or median"
  with the default reference "Ctrl"; it uses the mean, and the default is the first
  value of the first grouping column. Corrected in 0.6.0's notes (marked as such).

### Known issues

- **Windows:** the autosave fix of 0.6.0 for mapped network drives (#163) is not yet
  verified on Windows. Tools could stay in the "starting" state when FLIMAnalyzer
  started its own local Prefect server (#175); the Prefect server fix above (#195) may
  solve this, but it is not verified on Windows. Please report in the issues.
- **Docker CPU image** (added 2026-11-06): the CPU image `0.6.1-cpu` was not
  published. Its version label read `0.6.1-cpu` instead of `0.6.1`, so the check before
  publishing stopped it; `latest-cpu` is still 0.6.0. Use `0.6.0-cpu`, or the CUDA
  image `0.6.1`, until the next release, which fixes this.

## 0.6.0

The first release on current Python and package versions (Python 3.12, Prefect 3,
pandas 2, wxPython 4.2, PyTorch 2). FLIMAnalyzer is now installed with uv or pip (see
the README), instead of with the 0.5 series' `environment.yml`. The core (tools, workflows,
settings) is separate from the graphical user interface (GUI), so FLIMAnalyzer also runs
without it, in batch mode. Settings files of all earlier versions load.

### Results that change

- **Basic FLIRR Analysis** divides by the mean of a chosen reference category of the
  first grouping column (new setting "Reference value"; empty, the default, means that
  column's first value in category order). 0.5.x used the value in the first row as the
  reference, so results differ when the first row is not in the reference category
  (#157). *Corrected 2026-11-03: this entry first said "the mean or median" and
  "default "Ctrl""; the workflow always uses the mean, and "Ctrl" is the default of the
  Relative Change tool.*
- **Scatter, Box, Violin and Swarm plots** fit their value axes to the data (new
  setting "Fit axes to the data", on by default). In 0.5.x the axes always included 0,
  which squeezed data far from 0 (#158). Turn the setting off for the old axes.

### New

- **Batch mode:** `flimbatch` (or `flimanalyzer --batch`) imports data and runs tools
  and workflows without the GUI, e.g. on a computing cluster.
- **Installation without the GUI:** wxPython is optional (the `gui` extra), for
  computers without a display, such as cluster nodes.
- **Docker images** of batch mode on ghcr.io: `ghcr.io/uvakcci/flimanalyzer`, with
  the CUDA build of PyTorch or CPU only (`-cpu`).
- **PyPI:** FLIMAnalyzer is published on PyPI as `flimanalyzer`.
- **Concurrent and distributed execution:** steps that don't depend on each other run
  at the same time, as threads by default. Optional Dask executors run them in
  separate processes on one computer, or on a Dask cluster. Every task is tagged with
  its tool's name, so a Prefect concurrency limit on a tool (e.g. `Autoencoder: Train`)
  applies everywhere, also inside workflows.
- **Progress dialog:** shows the tasks, a link to Prefect and the folder the results are
  saved in, and has a Cancel button. Long folder paths are shortened, with the full
  path in the tooltip.
- **Run summary:** each step's status, resources and notes.
- **Tool dialogs** are redesigned: generated from the tools' settings, checked while
  typing, with markers for problems. Each dialog has Load Settings and Save Settings.
- **Settings files** have a section per tool. The File menu has Import Settings and
  Export Settings.
- **Workflows** check their settings against the data before they run, and suggest
  close column names when a column is missing.
- **Data tools:** new Split; Concatenate by rows or by columns; Unpivot by header
  level.
- **Plots** follow the category order on the axes and in the legends; legend position;
  several plots in one figure.
- **Autoencoder tools** use the GPU automatically (NVIDIA CUDA or Apple MPS) and fall
  back to the CPU.
- **Help menu** with links to the documentation and an About dialog. New icons in one
  colour-blind safe style.
- **Documentation:** user guide pages for batch mode, Docker, settings, the Filter
  tool, and concurrent and distributed execution (including `flimbatch` on HPC
  clusters with Slurm; those examples are not tested on a cluster). All screenshots
  are from 0.6.0. API reference.

### Fixes

- **Autosave to a mapped network drive** (Windows): the results were not saved in the
  chosen folder (#163). The folder is now stored as its full network path
  (`\\server\share\...`), and the dialogs and batch mode report a folder that can't be
  reached or written to before the run, instead of silently saving elsewhere. Not
  verified on Windows yet; please report in #163 whether it works for you.
- **Tall dialogs** (e.g. Tuning) no longer run off the screen: they scroll and fit the
  usable screen area, OK button included, also on small screens (#42).
- **AE Training** with the CPU selected warned about CUDA; the CPU path no longer
  queries CUDA (#143).
- **Filter Settings dialog:** the "Dropped view" column could show counts like `123:,`
  (#164).
- **Configuration dialogs** failed with wxPython 4.1 and later, so 0.5.x needs its
  pinned environment (#159). 0.6.0 runs on current wxPython (4.2).

### Removed

- The old plugin interface (#153). Tools are written against the new core interface;
  see the API reference.

## 0.5.2

Bug fixes for 0.5.1; no results change. Same requirements as 0.5.0 (`environment.yml`).

### Fixes

- **Import:** the Import dialog failed to open once the settings named a filename
  parser, e.g. after an import with one (#149).
- **Filter Settings dialog:** the title read "Filter Settings TEST" and the counts of
  dropped and remaining rows always showed "???" (#150).
- **Category filter** (right-click on a category column header): the values are listed
  in the category order set with Order Categories, not in the order they occur in the
  data (#151).
- **AE Training:** the default model "Autoencoder 2" does not exist; the default is now
  "AE Dimensionality Reduction 2-10". The dialog used to fall back to the first model;
  scripted use failed (#152).

## 0.5.1

Bug fixes for 0.5.0. Same requirements as 0.5.0: install with `environment.yml`
(Python 3.7, Prefect 1.3, pandas 1.1, wxPython 4.0.4, PyTorch 1.7). Newer wxPython
versions (4.1 and later) are not supported by the 0.5 series; FLIMAnalyzer 0.6 runs on
current Python and package versions.

### Results that change

- **FLIM Feature Analysis** used to skip every time point whose name contains "15"
  (e.g. "15 min", "T15"). All time points are now used, in the order of their
  categories (see Order Categories). Results of data sets with such time points differ
  from 0.5.0.
- **Line, Box, Swarm and Violin plots** follow the category order set with Order
  Categories, on the axes and in the legends. Line plots used to sort the x axis
  alphabetically.
- **AE Training** model files are named without a stray dot (`..._1e-08_epoch0001.model`,
  was `..._1e-0.8_epoch0001.model`). Existing model files keep their names and still
  load.
- **AE Training** saves the models on the CPU, so models trained on a GPU (cuda) load
  and run on any computer.

### Fixes

- **PCA:** when a selected feature has missing values, the principal components were
  put on the wrong rows (and categories); with one feature, a row number column was
  included in the PCA.
- **Frequency Histogram:** with two or more grouping columns, the legend labels were in
  a different order than the histograms, so series were mislabeled.
- **Frequency Histogram dialog:** the settings of FLIRR, NAD(P)H tm and other features
  with built-in defaults could not be opened; negative ranges can be entered; a
  feature without its own settings gets 100 bins (not the bins of the previous
  feature).
- **KDE:** "single plot" with one feature failed.
- **KS-Statistics:** failed when the only grouping column is the comparison column.
- **Random Forest:** failed when a grouping column is also a selected feature.
- **AE Augment:** the augmented table had an extra "index" feature column.
- **Bar plot:** a feature without values gives an empty plot instead of an error.
- **Import:** if no file can be read, a message is shown instead of an error; importing
  several files names the window "Imported Data" (not after the first file).
- **Saving a table** no longer changes the column names of the table shown, and works
  with columns whose names are not text.
- **Order Categories:** category settings no longer carry over from one data set to
  another.
- **Opening a file** no longer marks it as modified, so closing its window doesn't ask
  to save it.
- **Startup:** FLIMAnalyzer installed with `python setup.py install` failed to start
  unless run from inside the source folder (it looked for the version in a git
  checkout).

### Documentation

- The documentation builds on Read the Docs again (current build images; the 0.5.0
  configuration is no longer supported there).
