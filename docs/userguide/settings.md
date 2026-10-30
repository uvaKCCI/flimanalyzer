# Settings

FLIMAnalyzer saves its settings in JSON files: the import settings (delimiter, filename parser, renamed and dropped columns), the filters, and the settings of each tool, such as the grouping and features chosen in its dialog. The same files are used in [batch mode](/userguide/batch).

At startup, FLIMAnalyzer reads `defaults.json` in the folder it is started from, if there is one; otherwise it starts with the built-in defaults.

## The settings of the application

**Menu Access:** `File` > `Export Settings...` and `File` > `Import Settings...`

`Export Settings...` saves all current settings to a file. `Import Settings...` uses the settings in a file. A file that only has some of the settings, for example those of a single tool, changes only those; the other settings stay as they are.

Settings files of all FLIMAnalyzer versions can be imported, including those saved by FLIMAnalyzer 0.5; they are converted when they are read. Settings are always saved in the current format.

## The settings of a tool

Every tool's dialog has two buttons for its own settings:

* `Save Settings...` adds the tool's current settings to a settings file, or updates them there. Everything else in the file is kept, so the settings of several tools can be collected in one file, or added to a file saved with `Export Settings...`.
* `Load Settings...` reads the tool's settings from a settings file. The file can be one saved with `Save Settings...` or `Export Settings...`. If the file has no settings for the tool, the dialog says so.

The dialog's settings include whether the results are saved, and where.

## Settings of features

Some tools have a table with a row for each feature, for example the ranges and bins of the `Frequency Histogram`. `Load Feature Settings...` and `Save Feature Settings...` below the table read and save these values for each feature. `Load Feature Settings...` applies the values to the features in the table and keeps whether a feature is checked.

## Layout of a settings file

```
{
  "schema_version": 2,
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

Each tool has its own section under `tools`, named after the tool.
