# Settings

FLIMAnalyzer keeps its settings in JSON files. A settings file holds the range filters, the results folder, the executor, and the settings of each tool, such as the grouping and features chosen in its dialog. [Batch mode](/userguide/batch) uses the same files.

The range filters (see [Filtering Data](/userguide/data/filter.md#filtering-columns-with-numeric-values)) are part of the settings, as the `Filter` tool's feature filters. The values selected in category columns of a table window are not.

## Where the settings come from

The settings come from several layers. Each layer changes only the settings it has, and a higher layer takes precedence over a lower one. From lowest to highest:

1. The built-in defaults.
2. The [user settings file](#the-user-settings-file) (GUI only).
3. The [app settings file](#app-settings-files) given with `-s`.
4. [Environment variables](#environment-variables).
5. Command-line options (see [Command-line options](/install/index.md#command-line-options) and [Batch mode](/userguide/batch.md#options)).

Within a section, a higher layer changes:

* each entry on its own in `tools` and `presets` (per tool), `max_windows` (per kind of window), and `log` (per setting). For example, an app settings file with presets for `Filter` keeps your saved presets for `Calculate`, and one that sets only `log.dir` keeps your `log.max_age_days`.
* the whole section in `execution` (one executor with its options) and `filters` (one set of filters), and in all single settings.

`flimbatch` does not read the user settings file, so its results don't depend on settings changed in the GUI.

## Viewing the app settings

**Menu Access:** `File` > `Settings...` (on macOS: `FLIMAnalyzer` > `Settings...`)

The dialog lists the app settings of this session: the results folder, the executor, the Prefect server, the server timeout and the log folder. For each setting it shows:

* its value;
* where the value comes from: the built-in default, the user settings file, the app settings file, an environment variable or a command-line option;
* the command-line option and the environment variable that change it.

Below the table, it names the user settings file, your default app settings file if you have set one, the app settings file of the session, and the log file. Pointing at a row shows the setting's full value and its description.

The dialog only shows the settings. They apply when FLIMAnalyzer starts: to change them, start it with the command-line option, the environment variable, or an app settings file (`-s`) that sets them. The results folder can also be set for each run in a tool's dialog (`Save results`).

## The user settings file

The GUI saves the settings you change in it to the user settings file, automatically. These are the settings of the tool dialogs, including the folder under `Save results`, and the range filters. They apply again the next time the GUI starts. This includes the read settings and the workflow of `File` > `Import Tables...`, the settings of the `Import Tables` tool; the files you import are not saved.

The user settings file is `usersettings.json` in the platform's settings folder:

* macOS: `~/Library/Application Support/FLIMAnalyzer/usersettings.json`
* Linux: `~/.config/FLIMAnalyzer/usersettings.json`
* Windows: `%LOCALAPPDATA%\FLIMAnalyzer\usersettings.json`

The environment variable `FLIM_USER_SETTINGS` sets another path for this file.

If the user settings file can't be read, because it is damaged or comes from a newer FLIMAnalyzer version, the GUI renames it to `usersettings.unreadable.json` (`usersettings.unreadable-2.json` and so on if that name is taken), tells you, and starts a new user settings file. The renamed file is kept unchanged. If it comes from a newer version, rename it back before you use that version again. If the file can't be renamed either, the GUI keeps your changes only until it closes.

## App settings files

An app settings file is a settings file that you give with `-s` when you start the GUI or `flimbatch`, for example one saved with `Export Settings...`. Its settings apply to this session only. FLIMAnalyzer writes to this file only if you choose to update it to the current version (see [Settings files from older versions](#settings-files-from-older-versions)).

`-s` takes a path or a name:

* A path that exists as given, relative to the current folder or absolute, is used.
* Otherwise, the name is looked up in the folders of the app settings search path, as given and with `.json` added. For example, `-s cells` finds `cells.json`.
* If no file matches, or if files in several folders match, FLIMAnalyzer stops with an error. The message names the folders searched, or the files found.

The app settings search path is, in this order:

1. The folders in the environment variable `FLIM_APP_SETTINGS_PATH`, if it is set. The folders are separated by `:` on macOS and Linux, and by `;` on Windows.
2. Otherwise, the folders listed in `appsettings_path` in the user settings file.
3. Otherwise, the folder `appsettings` in the platform's settings folder, for example `~/Library/Application Support/FLIMAnalyzer/appsettings` on macOS.

`flimbatch` reads no user settings file, so it never uses `appsettings_path`: it searches the folders of `FLIM_APP_SETTINGS_PATH`, or else the default folder.

### Choosing an app settings file at startup

If you start the GUI without `-s`, and there is no `defaults.json` in the start folder, the GUI asks which app settings file to start with. The table lists the app settings files in the folders of the app settings search path, and your default app settings file if you have set one, with their folders. Tool and workflow files in these folders are not listed; the default has a check mark. `OK` starts with the selected file, and `Skip App Settings` (or Esc) starts without one. With a default, its row is selected, so pressing Enter starts with it; without one, no row is selected and Enter skips. If there are no files and no default, the GUI starts without asking. `flimbatch` never asks: it uses only the file given with `-s`. The `Description` column shows each file's `description`.

* `Make Default` makes the selected file your default from now on.
* `Clear Default` removes the default.
* `Browse...` adds a file from another folder to the table and selects it. If its folder is not in the app settings search path, the GUI asks whether to add it. The folder is then saved in the user settings file (`appsettings_path`), and the GUI lists its files at the next start.

The check mark moves at once. The change applies whether you then start with a file or skip; selecting a file alone doesn't change the default.

The default is saved in the user settings file (`default_app_settings`). If it no longer exists or can't be read, the GUI says so and removes it as the default. The chosen file is validated like a file given with `-s` (see [Settings files from older versions](#settings-files-from-older-versions)). If it can't be used, the GUI says why, and after `OK` it asks again.

### `defaults.json` (deprecated)

Before 0.7.0, the GUI read `defaults.json` in the folder it was started from. The GUI started without `-s` still uses a `defaults.json` in the start folder, as if it were given with `-s`, and shows a warning that this is deprecated. Started with `-s`, the GUI doesn't read `defaults.json`. To keep using the file, move it to a folder of the app settings search path, give it a name, for example `cells.json`, and start with `-s cells`.

## Environment variables

These environment variables set the same settings as the command-line options. They are read by the GUI and by `flimbatch`, except where the table says otherwise. `flimsettings env --list` lists them, with the commands that read each one (see [flimsettings](/userguide/flimsettings)).

| Variable | |
|---|---|
| `FLIM_RESULTS_DIR` | results folder, as `-o` (GUI only: `flimbatch` needs `-o`) |
| `FLIM_EXECUTION__EXECUTOR` | executor: `local`, `dask-local` or `dask`, as `-e` |
| `FLIM_EXECUTION__WORKERS` | number of workers of the executor |
| `FLIM_EXECUTION__SCHEDULER` | `threads` or `processes` (`dask-local`) |
| `FLIM_EXECUTION__ADDRESS` | address of the Dask cluster (`dask`) |
| `FLIM_EXECUTION` | the executor settings as JSON, instead of the four variables above, for example `{"executor": "dask-local", "workers": 8}` |
| `FLIM_PREFECT_SERVER` | `false` does the same as `--no-prefect-server` |
| `FLIM_SERVER_TIMEOUT` | how many seconds to wait for responses of the Prefect server, and of the Dask cluster if one is used, as `--server-timeout` |
| `FLIM_LOG_DIR` | log folder (`log` > `dir`), as `--log-dir` |
| `FLIM_LOG_LEVEL` | logging level, as `-l` (`--log-level`) |
| `FLIM_DRY_RUN` | `true` does the same as `--dry-run` (`flimbatch` only) |
| `FLIM_APP_SETTINGS_PATH` | the app settings search path (see [App settings files](#app-settings-files)), instead of `appsettings_path` and the default folder; also read by `flimsettings` |
| `FLIM_WORKFLOW_PATH` | the workflow search path: the folders searched for workflow files and tool files, instead of `workflow_paths` of the user settings file and the default folder; `-w` replaces it (see [Where workflow files are found](/userguide/workflows.md#where-workflow-files-are-found)); also read by `flimsettings` |
| `FLIM_USER_SETTINGS` | path of the user settings file (GUI and `flimsettings`) |

For example, on macOS and Linux:

```
export FLIM_EXECUTION__EXECUTOR=dask-local
export FLIM_EXECUTION__WORKERS=8
flimbatch -i data/ -o results/ --run summarize.json
```

## Saving and loading all settings

**Menu Access:** `File` > `Export Settings...` and `File` > `Import Settings...`

`Export Settings...` saves the settings as they are active now to an app settings file. After you choose the file, it asks for a description of the file (optional), for example a course or an experiment, and saves when you click `OK`. It saves every setting, whatever it comes from: the built-in defaults, your user settings file, the app settings file given with `-s`, an environment variable, a command-line option, or a change you made in the GUI. A value you gave only for this session is saved too, for example a results folder given with `-o`. Before you share the file or use it on another computer, check these values in the [Settings viewer](#viewing-the-app-settings), which shows where each value comes from. Four settings are left out, because they only have an effect in the user settings file: `appsettings_path`, `workflow_paths`, `default_app_settings` and `last_run_url`. Settings you change in the GUI after exporting are not added to the file; export again to save them there.

If the file's folder isn't in the app settings search path yet, it then asks whether to add it to `appsettings_path` in your user settings file, so that the GUI lists the file at startup and `-s` finds it by name. While `appsettings_path` is empty, the default folder is kept in the search path when a folder is added. The question doesn't appear while `FLIM_APP_SETTINGS_PATH` is set, because it replaces `appsettings_path`. The saved file includes the settings of every installed tool, with the tool's defaults if you haven't changed them, so that the file gives the same settings in a later FLIMAnalyzer version, even if the defaults change there. `Import Settings...` loads the settings from a file and uses them for this session; they are not saved to the user settings file. If a file has only some of the settings, for example those of a single tool, only those settings change. All other settings stay as they are.

You can import settings files from this and older FLIMAnalyzer versions, including FLIMAnalyzer 0.5 (see [Settings files from older versions](#settings-files-from-older-versions)). Settings are always saved in the current format.

## Settings files from older versions

Each time FLIMAnalyzer reads a settings file, it validates the file and converts its settings to the current format in memory. Reading a file doesn't change it. If a file of an older version can be used, the GUI asks whether to update it to the current format: at the start, in `File` > `Import Settings...` and in a tool dialog's `Load Settings...`. `Update` rewrites the file in the current format and keeps the original next to it, for example `lab.v1.json`, which the older FLIMAnalyzer version can still read. `Not Now` uses the file as it is, and the GUI asks again the next time. `flimsettings app --update FILE` and `flimsettings tool --update FILE` do the same from the command line. `flimbatch` never changes a settings file. The user settings file is updated when the GUI next saves a setting in it; before that, the GUI keeps the old file as `usersettings.v1.json`, for going back to the older FLIMAnalyzer. The validation sorts the settings into:

* settings converted to the current format, for example `working_dir`, which is now `results_dir`;
* settings removed because they are no longer used, for example `display`;
* unknown settings, which this version doesn't have, for example a misspelled name;
* invalid values, for example an executor that doesn't exist. The section with the invalid value, or the tool's settings, is not used;
* the settings of tools that aren't installed, which can't be validated. They are kept.

A file can't be used at all if it can't be read, isn't a settings file, or comes from a newer FLIMAnalyzer version.

If all settings can be used, the GUI uses the file and writes the result of the validation to the log. If some can't be used (unknown settings or invalid values), or the file can't be used at all, the GUI doesn't use the file. A message lists the problems: a warning for settings that can't be used, an error for a file that can't be used at all. `flimsettings app --validate FILE` lists all problems of a file.

* At the start (`-s`, `defaults.json` or the file chosen in the start dialog): after `OK`, the GUI asks again which app settings file to start with (see [Choosing an app settings file at startup](#choosing-an-app-settings-file-at-startup)). If there are no files to choose from, it starts without one.
* `File` > `Import Settings...` and a tool dialog's `Load Settings...`: nothing is loaded. Choose another file with the same command. In a tool dialog, only the tool's own settings count.

`flimbatch` uses a settings file only if every setting in it can be used and validated: it stops with an error that lists them if the file can't be used, or has invalid values, unknown settings or settings of tools that aren't installed. This way its results never depend on settings that were skipped, or on which tools are installed.

## The settings of a tool

Every tool's dialog has two buttons for its own settings:

* `Save Settings...` saves the tool's current settings. A new file, or an existing tool file, is written as a tool file: the tool's name, its `config` and `output` sections and, if it is set, its `processing` section, in the form of a step of a workflow file (see [Workflow files](/userguide/workflows.md#workflow-files)), without the folder. In an existing settings file, the tool's section is added or replaced. The file dialog starts in the workflow folder, the first folder of the workflow search path: there, `flimbatch --run FILE` finds the file by its file name. A new file in an app settings folder is saved only after a question, because app settings files are kept apart from tool and workflow files: `Use Workflow Folder` saves it in the workflow folder, `Save Here` in the chosen folder. Everything else in a settings file is kept, so the settings of several tools can be collected in one file, or added to a file saved with `Export Settings...`. If the file is from an older version or has settings that can't be used, the dialog lists them and asks first: update the file to the current version (the settings that can't be used are removed), or save to another file. `Cancel` saves nothing.
* `Load Settings...` reads the tool's settings from a settings file. The file can be one saved with `Save Settings...` or `Export Settings...`. If the file has no settings for the tool, the dialog says so.

The tool's settings also include whether its results are saved, to which folder and in which formats (its `output` section, see [Layout of a settings file](#layout-of-a-settings-file)). A tool file has no folder, because the folder is a setting of the computer.

If a results folder is set, a folder inside it is saved relative to it; any other folder is saved as it is (see [Saving results](/userguide/dialogs.md#saving-results)). On Windows, a folder on a mapped network drive (for example `Z:\results`) is saved as its network path (`\\server\share\results`). That way it still works when the drive letter is not available, for example when FLIMAnalyzer was started as administrator. If the folder can't be reached or written to, the dialog marks it and `OK` stays disabled.

## Settings of features

Some tools have a table with a row for each feature, for example the table of ranges and bins in the `Frequency Histogram` dialog. `Load Feature Settings...` and `Save Feature Settings...` below the table load and save these values for each feature. `Load Feature Settings...` applies the values to the features in the table. It does not change which features are checked.

## Layout of a settings file

The example shows an app settings file as `Export Settings...` writes it, shortened. A user settings file has the same layout, but it contains only the settings changed in the GUI.

```
{
  "schema_version": 2,
  "results_dir": "/Users/mst3k/results",
  "execution": {"executor": "local", "workers": null},
  "prefect_server": true,
  "log": {"dir": null, "max_age_days": 30},
  "filters": { ... },
  "tools": {
    "Summarize": {"config": { ... }, "output": {"save": false, "results_dir": null, "formats": []}},
    "K-Means": {"config": { ... }, "output": {"save": true, "results_dir": "results",
                "formats": [{"kind": "plot", "format": "svg"}]}},
    "Basic FLIRR Analysis": {"config": { ... }, "output": {"save": true, "results_dir": null, "formats": []},
                             "processing": {"strict": false}}
  }
}
```

* `schema_version`: the version of the file format. It is the first entry of the file.
* `description`: what the file is for, for example a course or an experiment (optional). `Export Settings...` asks for it; in the user settings file, edit it in the file. The GUI shows it when it asks which app settings file to start with.
* `results_dir`: the folder under `Save results` for tools that have no folder of their own. If it is not set (`null`), the results go to the folder FLIMAnalyzer was started from.
* `execution`: the executor and its options, as with `-e` (see [Concurrent and Distributed Execution](/userguide/execution)). For example, `{"executor": "dask-local", "workers": 8, "scheduler": "processes"}`, or `{"executor": "dask", "address": "tcp://host:8786"}`.
* `prefect_server`: `false` does the same as `--no-prefect-server`.
* `log`: the log folder (`dir`) and how many days the GUI keeps its log files (`max_age_days`). If the folder is not set (`null`), the GUI uses the platform's log folder, and `flimbatch` writes `flimbatch.log` into the results folder of the call (see [Log files](/install/index.md#log-files)).
* `appsettings_path`: the folders searched for app settings files. It is read only from the user settings file, because it is needed to find an app settings file; in an app settings file it is not used, and a message says so (see [App settings files](#app-settings-files)).
* `default_app_settings`: the app settings file selected when the GUI starts without `-s` (see [Choosing an app settings file at startup](#choosing-an-app-settings-file-at-startup)). It is read only from the user settings file; in an app settings file it is not used, and a message says so. `Export Settings...` leaves it, `appsettings_path`, `workflow_paths` and `last_run_url` out.
* `last_run_url`: the Prefect page of the last run the GUI started, opened by `Monitor` > `Last Run`. The GUI writes it after each run; it is read only from the user settings file, and in an app settings file it is not used, and a message says so.
* `workflow_paths`: the folders searched for workflow files and tool files by the GUI (see [Where workflow files are found](/userguide/workflows.md#where-workflow-files-are-found)). It is read only from the user settings file; in an app settings file it is not used, and a message says so. `-w` and `FLIM_WORKFLOW_PATH` replace it. `flimbatch` and `flimsettings` read no user settings file, so they don't use it.
* `favorites`: the names of the tools and workflows the tool panel shows, in order (see [Menus](/userguide/appmenu)). Empty: all tools. The GUI writes it to the user settings file with `File` > `Favorites...`; an app settings file can set it, for example for a course, and the user settings file takes precedence.
* `presets`: the presets saved with `Save as Preset...`, by tool name, for example `"Separate Categories": [{"name": "Mine", "settings": {...}}]`. A preset's `settings` are a part of the tool's settings. The `Calculate`, `Separate Categories` and `Filter` dialogs save them, and a table window's `Filter Features...` saves its range filters and `Filter Features` under `Filter`, as the `Filter` tool's `features` (see [Calculate](/userguide/analysis/calculate.md), [Separate Categories](/userguide/data/separate.md#presets) and [Filtering Data](/userguide/data/filter.md#presets)). The GUI writes them to the user settings file.
* `max_windows`: per kind of result, the most windows that a run of `Import Tables` or of a workflow file in the GUI may open, by default `{"table": 10, "plot": 10, "image": 4}`; such a run that would open more doesn't start (see [Import Tables](/userguide/data/load.md#import-tables)). Other tools and workflows are not limited. The GUI doesn't change it; set it in an app settings file.
* `filters`: the switches that new table windows start with: `features` (`Filter Features`, `{"enabled": true}` to use the range filters) and `categories` (`Filter Categories`, the category values hidden through a column header), both off by default, and whether the dropped rows are shown (`show_dropped`). They apply only to the table windows; `flimbatch` doesn't use them: to filter rows in a batch run, add a `Filter` step to a workflow file. The filters themselves are the settings of the `Filter` tool, in `tools` (see [Filter Tool](/userguide/data/filtertool.md#filters-in-settings-files)).
* `server_timeout`: how many seconds to wait for responses of the Prefect server, and of the Dask cluster if one is used, as `--server-timeout`. Default: 60.
* `tools`: each tool has its own section, named after the tool, with its settings (`config`), its `output` section and, if it is set, its `processing` section. `output` is whether its results are saved (`save`), in which folder (`results_dir`: `null` for the default results folder, a relative path such as `"results"` for a folder inside it, which moves with it, or an absolute path), and in which formats (`formats`, one entry per format with its `kind` and `format`, for example `{"kind": "table", "format": "csv"}`; a kind not listed is saved in its default format, and a kind the tool doesn't make is an invalid value), and the text replaced in the names of the files and folders its results are saved in (`char_replacements`, as in a workflow file's `output`, see [Workflow files](/userguide/workflows.md#workflow-files); not set: the built-in replacements). The tool's dialog doesn't show `char_replacements`; it keeps the value of the settings file. `processing` is how a run treats data that doesn't match the settings, as in a step of a workflow file (see `processing` under [Workflow files](/userguide/workflows.md#workflow-files)).

Older files are converted when they are read: `working_dir` becomes `results_dir`, a tool's `autosave` and `results_dir` become its `output` section (`save` and `results_dir`, with the default formats), `strict` in a tool's `config` becomes its `processing` > `strict` (`null` is dropped, because strict is the default), `rescale` in the autoencoder training settings becomes `rescale_output`, the `preprocess` section becomes the settings of the `Rename Columns`, `Drop Columns` and `Calculate` tools (each dropped text with the match `contains`, each calculation a `function` row, in the order `Import...` of FLIMAnalyzer 0.6 calculated them), the range filters in `filters` become the `Filter` tool's range filters (each switched on as it was selected; the `Filter` tool's own filters of the older file are added switched off), `filters` > `use` (`Filter Data`) becomes `filters` > `features` (`Filter Features`), the `Filter` tool's filters are put into its three parts by kind (a second filter on a column goes to `other`, see [Filter Tool](/userguide/data/filtertool.md#filters-in-settings-files)), and `display`, which is no longer used, is dropped.

The `import` section of FLIMAnalyzer 0.6 (the delimiter, the filename parser and its patterns, the files left out and the column combinations) is not used any more: what is done with data files is a [workflow file](/userguide/workflows.md#workflow-files)'s. When the GUI uses such a file (with `-s`, at startup, or with `File` > `Import Settings...`), it offers to save these settings, together with the file's renamed, dropped and calculated columns, as a workflow file that imports as FLIMAnalyzer 0.6 did, for example `Import (lab-settings)`. If you save it, `File` > `Import Tables...` runs it next, and reads the files with the file's delimiter and files left out. Nothing is applied unless you save it. `flimbatch` says that the settings are not used.
