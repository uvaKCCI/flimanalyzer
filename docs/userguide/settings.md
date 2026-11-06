# Settings

FLIMAnalyzer saves its settings in JSON files. A settings file holds the import settings (delimiter, filename parser, renamed and dropped columns), the range filters, the default results folder, and the settings of each tool, such as the grouping and features chosen in its dialog. [Batch mode](/userguide/batch) uses the same files.

At startup, FLIMAnalyzer reads `defaults.json` in the folder it is started from, if there is one; otherwise it starts with the built-in defaults. To start with another settings file, give it with `-c` (see [Command-line options](/install/index.md#command-line-options)); `defaults.json` is then not read.

FLIMAnalyzer does not save the settings when it closes. Changes, for example the settings of a tool's dialog, are kept only while it is open. To keep them, save them with `Export Settings...`, for example as `defaults.json` in the folder you start FLIMAnalyzer from.

The range filters (see [Filtering Data](/userguide/data/filter.md#filtering-columns-with-numeric-values)) are part of the settings. The values selected in category columns are not.

## Saving and loading all settings

**Menu Access:** `File` > `Export Settings...` and `File` > `Import Settings...`

`Export Settings...` saves all current settings to a file. `Import Settings...` loads the settings from a file and uses them. If a file has only some of the settings, for example those of a single tool, only those settings change. All other settings stay as they are.

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
  "schema_version": 1,
  "working_dir": "/Users/mst3k/FLIMAnalyzerResults",
  "import": { ... },
  "preprocess": { ... },
  "display": [ ... ],
  "filters": { ... },
  "tools": {
    "Summarize": {"config": { ... }, "autosave": false, "results_dir": null},
    "K-Means": {"config": { ... }, "autosave": true, "results_dir": "results"}
  }
}
```

* `schema_version`: the version of the file format.
* `working_dir`: the folder under `Save results in` for tools that have no folder of their own. Default: `FLIMAnalyzerResults` in your home folder.
* `import` and `preprocess`: the import settings.
* `display`: not used by this version of FLIMAnalyzer.
* `filters`: the range filters, and whether they are switched on.
* `tools`: each tool has its own section, named after the tool, with its settings (`config`), whether its results are saved (`autosave`) and in which folder (`results_dir`).
