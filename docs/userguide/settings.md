# Settings

FLIMAnalyzer keeps its settings in JSON files. A settings file holds the import settings (delimiter, filename parser, renamed and dropped columns), the range filters, the results folder, the executor, and the settings of each tool, such as the grouping and features chosen in its dialog. [Batch mode](/userguide/batch) uses the same files.

The range filters (see [Filtering Data](/userguide/data/filter.md#filtering-columns-with-numeric-values)) are part of the settings. The values selected in category columns are not.

## Where the settings come from

The settings come from several layers. Each layer changes only the settings it has, and a higher layer takes precedence over a lower one. From lowest to highest:

1. The built-in defaults.
2. The [user settings file](#the-user-settings-file) (GUI only).
3. The [app settings file](#app-settings-files) given with `-s`.
4. [Environment variables](#environment-variables).
5. Command-line options (see [Command-line options](/install/index.md#command-line-options) and [Batch mode](/userguide/batch.md#options)).

`flimbatch` does not read the user settings file, so its results don't depend on settings changed in the GUI.

## The user settings file

The GUI saves the settings you change in it to the user settings file, automatically. These are the settings of the tool dialogs, including the folder under `Save results in`, and the range filters. They apply again the next time the GUI starts. The import settings are kept only while the GUI is open.

The user settings file is `usersettings.json` in the platform's settings folder:

* macOS: `~/Library/Application Support/FLIMAnalyzer/usersettings.json`
* Linux: `~/.config/FLIMAnalyzer/usersettings.json`
* Windows: `%LOCALAPPDATA%\FLIMAnalyzer\usersettings.json`

The environment variable `FLIM_USER_SETTINGS` sets another path for this file.

### `defaults.json` (deprecated)

Before 0.7.0, the GUI read the settings in `defaults.json` in the folder it was started from. The user settings file replaces it. If there is a `defaults.json` in the start folder and no user settings file yet, the GUI copies the settings of `defaults.json` into a new user settings file and doesn't read `defaults.json` again. Settings that this version doesn't have are not copied. It shows a warning whenever it finds a `defaults.json`.

To use the settings of a `defaults.json` with `-s` instead, move it to an app settings folder and give it a name, for example `cells.json`, and start with `-s cells`.

## App settings files

An app settings file is a settings file that you give with `-s` when you start the GUI or `flimbatch`, for example one saved with `Export Settings...`. Its settings apply to this session only. FLIMAnalyzer never writes to this file.

`-s` takes a path or a name:

* A path that exists as given, relative to the current folder or absolute, is used.
* Otherwise, the name is looked up in the app settings folders, as given and with `.json` added. For example, `-s cells` finds `cells.json`.
* If no file matches, or if files in several folders match, FLIMAnalyzer stops with an error. The message names the folders searched, or the files found.

The app settings folders are, in this order:

1. The folders in the environment variable `FLIM_APP_SETTINGS_PATH`, if it is set. The folders are separated by `:` on macOS and Linux, and by `;` on Windows.
2. Otherwise, the folders listed in `appsettings_path` in the user settings file.
3. Otherwise, the folder `appsettings` in the platform's settings folder, for example `~/Library/Application Support/FLIMAnalyzer/appsettings` on macOS.

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
| `FLIM_LOG_DIR` | log folder setting, as `--log-dir` |
| `FLIM_CACHE_DIR` | cache folder setting, as `--cache-dir` |
| `FLIM_STRICT` | `true` or `false`, as `--strict` or `--no-strict` |
| `FLIM_APP_SETTINGS_PATH` | the app settings folders (see [App settings files](#app-settings-files)), instead of `appsettings_path` and the default folder |
| `FLIM_USER_SETTINGS` | path of the user settings file (GUI) |

For example, on macOS and Linux:

```
export FLIM_EXECUTION__EXECUTOR=dask-local
export FLIM_EXECUTION__WORKERS=8
flimbatch -i data/ -o results/ -s settings.json --run Summarize
```

## Saving and loading all settings

**Menu Access:** `File` > `Export Settings...` and `File` > `Import Settings...`

`Export Settings...` saves all current settings to a file. `Import Settings...` loads the settings from a file and uses them for this session; they are not saved to the user settings file. If a file has only some of the settings, for example those of a single tool, only those settings change. All other settings stay as they are.

You can import settings files from this and older FLIMAnalyzer versions, including FLIMAnalyzer 0.5. Older files are converted when they are read. Files from a newer FLIMAnalyzer version, with a newer `schema_version`, are refused with a message to update FLIMAnalyzer. Settings are always saved in the current format.

## The settings of a tool

Every tool's dialog has two buttons for its own settings:

* `Save Settings...` adds the tool's current settings to a settings file, or updates them there. Everything else in the file is kept, so the settings of several tools can be collected in one file, or added to a file saved with `Export Settings...`.
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
  "log_dir": null,
  "cache": {"dir": null, "max_size_mb": 2048, "max_age_days": 7},
  "strict": null,
  "appsettings_path": [],
  "import": { ... },
  "preprocess": { ... },
  "filters": { ... },
  "tools": {
    "Summarize": {"config": { ... }, "autosave": false, "results_dir": null},
    "K-Means": {"config": { ... }, "autosave": true, "results_dir": "results"}
  }
}
```

* `schema_version`: the version of the file format.
* `results_dir`: the folder under `Save results in` for tools that have no folder of their own. If it is not set (`null`), the results go to the folder FLIMAnalyzer was started from.
* `execution`: the executor and its options, as with `-e` (see [Concurrent and Distributed Execution](/userguide/execution)). For example, `{"executor": "dask-local", "workers": 8, "scheduler": "processes"}`, or `{"executor": "dask", "address": "tcp://host:8786"}`.
* `prefect_server`: `false` does the same as `--no-prefect-server`.
* `log_dir`: the log folder setting.
* `cache`: the cache folder setting (`dir`), the maximum cache size in MB (`max_size_mb`) and the maximum age of cached items in days (`max_age_days`).
* `strict`: workflows: `true` makes columns that are not in the data errors; `false` replaces them by the closest matching column. A workflow's own `Strict` setting takes precedence. If it is not set (`null`), missing columns are guessed in the GUI, where the guesses are shown before the run, and are errors in `flimbatch`.
* `appsettings_path`: the folders searched for app settings files. It is read from the user settings file (see [App settings files](#app-settings-files)).
* `import` and `preprocess`: the import settings.
* `filters`: the range filters, and whether they are switched on.
* `tools`: each tool has its own section, named after the tool, with its settings (`config`), whether its results are saved (`autosave`) and in which folder (`results_dir`).

Older files are converted when they are read: `working_dir` becomes `results_dir`, and `display`, which is no longer used, is dropped.
