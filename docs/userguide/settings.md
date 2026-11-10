# Settings

FLIMAnalyzer keeps its settings in JSON files. A settings file holds the range filters, the results folder, the executor, and the settings of each tool, such as the grouping and features chosen in its dialog. [Batch mode](/userguide/batch) uses the same files.

The range filters (see [Filtering Data](/userguide/data/filter.md#filtering-columns-with-numeric-values)) are part of the settings, as the `Filter` tool's filters. The values selected in category columns of a table window are not.

## Where the settings come from

The settings come from several layers. Each layer changes only the settings it has, and a higher layer takes precedence over a lower one. From lowest to highest:

1. The built-in defaults.
2. The [user settings file](#the-user-settings-file) (GUI only).
3. The [app settings file](#app-settings-files) given with `-s`.
4. [Environment variables](#environment-variables).
5. Command-line options (see [Command-line options](/install/index.md#command-line-options) and [Batch mode](/userguide/batch.md#options)).

`flimbatch` does not read the user settings file, so its results don't depend on settings changed in the GUI.

## Viewing the app settings

**Menu Access:** `File` > `Settings...` (on macOS: `FLIMAnalyzer` > `Settings...`)

The dialog lists the app settings of this session: the results folder, the executor, the Prefect server, the log folder and how workflows handle missing columns. For each setting it shows:

* its value;
* where the value comes from: the built-in default, the user settings file, the app settings file, an environment variable or a command-line option;
* the command-line option and the environment variable that change it.

Below the table, it names the user settings file, your default app settings file if you have set one, the app settings file of the session, and the log file. Pointing at a row shows the setting's full value and its description.

The dialog only shows the settings. They apply when FLIMAnalyzer starts: to change them, start it with the command-line option, the environment variable, or an app settings file (`-s`) that sets them. The results folder can also be set for each run in a tool's dialog (`Save results in`).

## The user settings file

The GUI saves the settings you change in it to the user settings file, automatically. These are the settings of the tool dialogs, including the folder under `Save results in`, and the range filters. They apply again the next time the GUI starts. This includes the settings of `File` > `Import...` (the Import tool's: delimiter, filename parser, files to leave out); the files you import are not saved.

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

### Choosing an app settings file at startup

If you start the GUI without `-s`, and there is no `defaults.json` in the start folder, the GUI asks which app settings file to start with. The table lists the `.json` files in the folders of the app settings search path, and your default app settings file if you have set one, with their folders; the default has a check mark. `OK` starts with the selected file, and `Skip App Settings` (or Esc) starts without one. With a default, its row is selected, so pressing Enter starts with it; without one, no row is selected and Enter skips. If there are no files and no default, the GUI starts without asking. `flimbatch` never asks: it uses only the file given with `-s`.

* `Make Default` makes the selected file your default from now on.
* `Clear Default` removes the default.

The check mark moves at once. The change applies whether you then start with a file or skip; selecting a file alone doesn't change the default.

The default is saved in the user settings file (`default_app_settings`). If it no longer exists or can't be read, the GUI says so and removes it as the default. The chosen file is checked like a file given with `-s` (see [Settings files from older versions](#settings-files-from-older-versions)).

### `defaults.json` (deprecated)

Before 0.7.0, the GUI read `defaults.json` in the folder it was started from. The GUI started without `-s` still uses a `defaults.json` in the start folder, as if it were given with `-s`, and shows a warning that this is deprecated. Started with `-s`, the GUI doesn't read `defaults.json`. To keep using the file, move it to a folder of the app settings search path, give it a name, for example `cells.json`, and start with `-s cells`.

## Environment variables

These environment variables set the same settings as the command-line options. They are read by the GUI and by `flimbatch`.

| Variable | |
|---|---|
| `FLIM_RESULTS_DIR` | results folder, as `-o` |
| `FLIM_EXECUTION__EXECUTOR` | executor: `local`, `dask-local` or `dask`, as `-e` |
| `FLIM_EXECUTION__WORKERS` | number of workers of the executor |
| `FLIM_EXECUTION__SCHEDULER` | `threads` or `processes` (`dask-local`) |
| `FLIM_EXECUTION__ADDRESS` | address of the Dask cluster (`dask`) |
| `FLIM_EXECUTION` | the executor settings as JSON, instead of the four variables above, for example `{"executor": "dask-local", "workers": 8}` |
| `FLIM_PREFECT_SERVER` | `false` does the same as `--no-prefect-server` |
| `FLIM_LOG_DIR` | log folder (`log` > `dir`), as `--log-dir` |
| `FLIM_CACHE_DIR` | cache folder setting, as `--cache-dir` |
| `FLIM_STRICT` | `true` or `false`, as `--strict` or `--no-strict` |
| `FLIM_APP_SETTINGS_PATH` | the app settings search path (see [App settings files](#app-settings-files)), instead of `appsettings_path` and the default folder |
| `FLIM_USER_SETTINGS` | path of the user settings file (GUI) |

For example, on macOS and Linux:

```
export FLIM_EXECUTION__EXECUTOR=dask-local
export FLIM_EXECUTION__WORKERS=8
flimbatch -i data/ -o results/ -s settings.json --run Summarize
```

## Saving and loading all settings

**Menu Access:** `File` > `Export Settings...` and `File` > `Import Settings...`

`Export Settings...` saves all current settings to a file. If the file's folder isn't in the app settings search path yet, it then asks whether to add it to `appsettings_path` in your user settings file, so that the GUI lists the file at startup and `-s` finds it by name. While `appsettings_path` is empty, the default folder is kept in the search path when a folder is added. The question doesn't appear while `FLIM_APP_SETTINGS_PATH` is set, because it replaces `appsettings_path`. It includes the settings of every installed tool, with the tool's defaults if you haven't changed them, so that the file gives the same settings in a later FLIMAnalyzer version, even if the defaults change there. `appsettings_path` is not saved: it only has an effect in the user settings file. `Import Settings...` loads the settings from a file and uses them for this session; they are not saved to the user settings file. If a file has only some of the settings, for example those of a single tool, only those settings change. All other settings stay as they are.

You can import settings files from this and older FLIMAnalyzer versions, including FLIMAnalyzer 0.5 (see [Settings files from older versions](#settings-files-from-older-versions)). Settings are always saved in the current format.

## Settings files from older versions

Each time FLIMAnalyzer reads a settings file, it checks the file and converts its settings to the current format in memory. Reading a file doesn't change it. The check sorts the settings into:

* settings converted to the current format, for example `working_dir`, which is now `results_dir`;
* settings removed because they are no longer used, for example `display`;
* unknown settings, which this version doesn't have, for example a misspelled name;
* invalid values, for example an executor that doesn't exist. The section with the invalid value, or the tool's settings, is not used;
* the settings of tools that aren't installed, which can't be checked. They are kept.

A file can't be used at all if it can't be read, isn't a settings file, or comes from a newer FLIMAnalyzer version.

If all settings can be used, the GUI uses the file and writes the result of the check to the log. If some can't be used, the GUI lists them and asks what to do:

* `Use the settings that can be used; skip the others`
* `Don't use this file`
* `Update the file to the current version; remove the settings that can't be used`: after a confirmation, the file is replaced by its usable settings in the current format. The removed settings can't be recovered.
* `Choose another file...`: the other file is checked in the same way.

`Cancel` doesn't use the file. A file that can't be used at all offers only the last two choices.

The GUI asks this when it starts with `-s` (or with `defaults.json`), in `File` > `Import Settings...`, and in a tool dialog's `Load Settings...`. In a tool dialog, it asks only if the tool's own settings have problems.

`flimbatch` doesn't ask. It uses a settings file only if every setting in it can be used and checked: it stops with an error that lists them if the file can't be used, or has invalid values, unknown settings or settings of tools that aren't installed. This way its results never depend on settings that were skipped, or on which tools are installed.

## The settings of a tool

Every tool's dialog has two buttons for its own settings:

* `Save Settings...` adds the tool's current settings to a settings file, or updates them there. Everything else in the file is kept, so the settings of several tools can be collected in one file, or added to a file saved with `Export Settings...`. If the file is from an older version or has settings that can't be used, the dialog lists them and asks first: update the file to the current version (the settings that can't be used are removed), or save to another file. `Cancel` saves nothing.
* `Load Settings...` reads the tool's settings from a settings file. The file can be one saved with `Save Settings...` or `Export Settings...`. If the file has no settings for the tool, the dialog says so.

The tool's settings also include whether its results are saved, and to which folder.

The folder is saved as its full path. On Windows, a folder on a mapped network drive (for example `Z:\results`) is saved as its network path (`\\server\share\results`). That way it still works when the drive letter is not available, for example when FLIMAnalyzer was started as administrator. If the folder can't be reached or written to, the dialog marks it and `OK` stays disabled.

## Settings of features

Some tools have a table with a row for each feature, for example the table of ranges and bins in the `Frequency Histogram` dialog. `Load Feature Settings...` and `Save Feature Settings...` below the table load and save these values for each feature. `Load Feature Settings...` applies the values to the features in the table. It does not change which features are checked.

## Layout of a settings file

```
{
  "schema_version": 2,
  "results_dir": "/Users/mst3k/results",
  "execution": {"executor": "local", "workers": null},
  "prefect_server": true,
  "log": {"dir": null, "max_age_days": 30},
  "cache": {"dir": null, "max_size_mb": 2048, "max_age_days": 7},
  "strict": null,
  "appsettings_path": [],
  "filters": { ... },
  "tools": {
    "Summarize": {"config": { ... }, "autosave": {"enabled": false, "results_dir": null, "formats": []}},
    "K-Means": {"config": { ... }, "autosave": {"enabled": true, "results_dir": "results",
                "formats": [{"kind": "plot", "format": "svg"}]}}
  }
}
```

* `schema_version`: the version of the file format.
* `results_dir`: the folder under `Save results in` for tools that have no folder of their own. If it is not set (`null`), the results go to the folder FLIMAnalyzer was started from.
* `execution`: the executor and its options, as with `-e` (see [Concurrent and Distributed Execution](/userguide/execution)). For example, `{"executor": "dask-local", "workers": 8, "scheduler": "processes"}`, or `{"executor": "dask", "address": "tcp://host:8786"}`.
* `prefect_server`: `false` does the same as `--no-prefect-server`.
* `log`: the log folder (`dir`) and how many days the GUI keeps its log files (`max_age_days`). If the folder is not set (`null`), the GUI uses the platform's log folder and `flimbatch` its output folder (see [Log files](/install/index.md#log-files)).
* `cache`: the cache folder setting (`dir`), the maximum cache size in MB (`max_size_mb`) and the maximum age of cached items in days (`max_age_days`).
* `strict`: workflows: `true` makes columns that are not in the data errors; `false` replaces them by the closest matching column. A workflow's own `Strict` setting takes precedence. If it is not set (`null`), missing columns are guessed in the GUI, where the guesses are shown before the run, and are errors in `flimbatch`.
* `appsettings_path`: the folders searched for app settings files. It is read from the user settings file (see [App settings files](#app-settings-files)).
* `default_app_settings`: the app settings file selected when the GUI starts without `-s` (see [Choosing an app settings file at startup](#choosing-an-app-settings-file-at-startup)). It is read from the user settings file. `Export Settings...` leaves it and `appsettings_path` out.
* The settings of `File` > `Import...` are the `Import` tool's, in `tools`: `delimiter`, `exclude_files`, `parser`, `patterns`, `category_combinations`, and `clash_name` and `clash_renames` (see [The Source column](/userguide/data/load.md#the-source-column)). The columns `Import...` renames, drops and calculates are the settings of the `Rename Columns`, `Drop Columns` and `Calculate` tools.
* `filters`: whether the table windows filter their rows (`use`, also used by `flimbatch` after the import) and show the dropped rows (`show_dropped`). The filters themselves are the settings of the `Filter` tool, in `tools` (see [Filter Tool](/userguide/data/filtertool.md#filters-in-settings-files)).
* `tools`: each tool has its own section, named after the tool, with its settings (`config`) and its `autosave` section: whether its results are saved (`enabled`), in which folder (`results_dir`), and in which formats (`formats`, one entry per format with its `kind` and `format`, for example `{"kind": "table", "format": "csv"}`; a kind not listed is saved in its default format).

Older files are converted when they are read: `working_dir` becomes `results_dir`, a tool's `autosave` and `results_dir` become its `autosave` section (with the default formats, as before), the `preprocess` section becomes the settings of the `Rename Columns`, `Drop Columns` and `Calculate` tools (each dropped text with the match `contains`, each calculation a `function` row, in the order `Import...` calculates them), the `import` section becomes the `Import` tool's settings (its list of the last imported files is dropped), the range filters in `filters` become the `Filter` tool's filters (each switched on as it was selected; the `Filter` tool's own filters of the older file are added switched off), and `display`, which is no longer used, is dropped.
