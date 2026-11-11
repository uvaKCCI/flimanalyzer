# Separate Categories

The `Separate Categories` tool separates one category or text column into several category columns, for example `FOV:Cell` back into `FOV` and `Cell`, or a file name such as `Results-ko_01.txt` into `Treatment` `ko` and `Cell` `01`. It has two modes: at delimiters, or by patterns.

**Menu Access:** `Data` > `Separate Categories`

**Tool panel icon:** ![](/images/data/separate.png)

1. Select `Data` > `Separate Categories`.

2. In the `Configuration: Separate Categories` dialog, set:

    - `Column`: the category or text column to separate, for example `Source`. Values that are file URIs (`file:///...`, see [The Source column](load.md#the-source-column)) are separated as their paths, with special characters decoded (`%20` as a space).
    - `Separate`: `delimiters` or `patterns` (see below).
    - `Part`: which part of the values to separate: the whole `value`, or, for a path, its `file name`, with or without its extension.
    - `Keep the original column` (checked by default): unchecked, the separated column is removed.

    Below the settings, the dialog shows an example from the first row, for example `Example: /data/Results-ko_01.txt → Treatment ko, Cell 01`, and warns about values that can't be separated as set.

3. Click `OK`.

The result is `Table: Separated`, with the new columns after the separated column.

## At delimiters

The values are separated at any of the `Delimiters` (default `:`, the reverse of `Fuse Categories`).

- `New columns`: the names of the new columns, one per part, in order. An empty name skips that part. If you give no names, they come from the column name separated the same way: `FOV:Cell` gives `FOV` and `Cell`.

A value with more or fewer parts than there are names is not separated: its row gets missing values in the new columns, so that no part ends up in the wrong column. The run summary lists these values.

For example, to separate file names like `Results-ko_01.txt`: `Part` `file name without extension`, `Delimiters` `-` and `_`, and `New columns` empty, `Treatment`, `Cell` (the empty name skips `Results`).

## By patterns

Each pattern makes one new column: its name, and a regular expression whose first group, in parentheses, is the value. The filename parsers of FLIMAnalyzer 0.6 are presets with such patterns (see [Presets](#presets)). For example, the pattern `/data/(.*?)/` takes `ctrl` from `/data/ctrl/FOV1/cell3.txt`. Backslashes in Windows paths are matched as `/`.

A group that matches nothing gives `?`. A value that the pattern doesn't match gets a missing value. The run summary reports a pattern that matched no value at all.

## Presets

The buttons below the settings load and save presets: settings for how to separate, by name.

* `Load Preset...` fills in the settings of a preset: the column, the mode, the part, the delimiters, the new columns' names and the patterns. The other settings stay as they are.
* `Save as Preset...` saves these settings of the dialog as a preset of your own, in the user settings file (`separate_presets`). A preset with the same name is replaced; the names of the built-in presets can't be used.
* `Remove Presets...` removes presets you saved. The built-in ones can't be removed.

The built-in presets are the filename parsers of FLIMAnalyzer 0.6, as patterns on the `Source` column, named after the categories they take from the file paths: `FOV, Treatment, Cell`, `Treatment, FOV, Cell`, `Treatment, FOV, Time`, `Treatment, Time`, `FOV, Time, Well`, `Compartment, FOV, Treatment, Cell`, `Compartment, Treatment, FOV, Cell` and `Cell line, Compartment, FOV, Treatment, Cell`. For example, `FOV, Treatment, Cell` reads `FOV` `a`, `Treatment` `ctrl` and `Cell` `1` from `Results-a-ctrl-1.txt`, with these patterns:

```
{"name": "FOV", "regex": ".*/.*?[_-](.*?)[_-]"}
{"name": "Treatment", "regex": ".*/.*?[_-].*?[_-](.*?)[_-]"}
{"name": "Cell", "regex": ".*/.*?[_-].*?[_-].*?[_-](\\d*?)\\."}
```

To take categories from the file names in every import, also in [batch mode](/userguide/batch), copy the built-in `Import` workflow (see [Workflow files](/userguide/workflows.md#workflow-files)) and add a step before `Calculate`, for example:

```
{"id": "5", "tool": "Separate Categories", "config": {"column": "Source", "mode": "patterns", "patterns": [ ... ]}}
```

with the patterns of the preset; the ids of the steps after it change accordingly.
