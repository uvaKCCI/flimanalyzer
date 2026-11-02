# Settings

FLIMAnalyzer saves its settings in JSON files. A settings file holds the import settings (delimiter, filename parser, renamed and dropped columns), the filters, and the settings of each tool, such as the grouping and features chosen in its dialog. [Batch mode](/userguide/batch) uses the same files.

At startup, FLIMAnalyzer reads `defaults.json` in the folder it is started from, if there is one; otherwise it starts with the built-in defaults.

## Saving and loading all settings

**Menu Access:** `File` > `Export Settings...` and `File` > `Import Settings...`

`Export Settings...` saves all current settings to a file. `Import Settings...` loads the settings from a file and uses them. If a file has only some of the settings, for example those of a single tool, only those settings change. All other settings stay as they are.

You can import settings files from any FLIMAnalyzer version, including FLIMAnalyzer 0.5. Older files are converted when they are read. Settings are always saved in the current format.

## The settings of a tool

Every tool's dialog has two buttons for its own settings:

* `Save Settings...` adds the tool's current settings to a settings file, or updates them there. Everything else in the file is kept, so the settings of several tools can be collected in one file, or added to a file saved with `Export Settings...`.
* `Load Settings...` reads the tool's settings from a settings file. The file can be one saved with `Save Settings...` or `Export Settings...`. If the file has no settings for the tool, the dialog says so.

The tool's settings also include whether its results are saved, and to which folder.

## Settings of features

Some tools have a table with a row for each feature, for example the table of ranges and bins in the `Frequency Histogram` dialog. `Load Feature Settings...` and `Save Feature Settings...` below the table load and save these values for each feature. `Load Feature Settings...` applies the values to the features in the table. It does not change which features are checked.

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
