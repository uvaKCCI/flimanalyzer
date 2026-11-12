# Separate Categories

The `Separate Categories` tool separates one category or text column into several category columns, for example `FOV:Cell` back into `FOV` and `Cell`, or a file name such as `Results-ko_01.txt` into `Treatment` `ko` and `Cell` `01`. It has three modes: at delimiters, by a template of the values, or by patterns (regular expressions).

**Menu Access:** `Data` > `Separate Categories`

**Tool panel icon:** ![](/images/data/separate.png)

1. Select `Data` > `Separate Categories`.

2. In the `Configuration: Separate Categories` dialog, set:

    - `Column`: the category or text column to separate, for example `Source`. Values that are file URIs (`file:///...`, see [The Source column](load.md#the-source-column)) are separated as their paths, with special characters decoded (`%20` as a space).
    - `Mode`: `delimiter`, `template` or `pattern` (see below). The dialog shows only the settings of the chosen mode.
    - `Part`: which part of the values to separate: the whole `value`, or, for a path, its `file name`, with or without its extension.
    - `Keep the original column` (checked by default): unchecked, the separated column is removed.

    Below the settings, the dialog shows an example from the first row, for example `Example: file:///data/Results-ko_01.txt → Treatment ko, Cell 01`. The example shows the value as it is in the column, also when `Part` separates only its file name. The dialog also warns about values that can't be separated as set.

3. Click `OK`.

The result is `Table: Separated`, with the new columns after the separated column.

## At delimiters

Mode `delimiter`: the values are separated at any of the `Delimiters` (default `:`, the reverse of `Fuse Categories`). Type the delimiters one after the other, each a single character, for example `-_` for `-` or `_`; a tab is typed `\t`. A delimiter of several characters, such as `::`, can be given as a list, `["::", "-"]`.

- `New columns`: the names of the new columns, one per part, in order, separated by commas. An empty name skips that part, for example `, Treatment, Cell`. If you give no names, they come from the column name separated the same way: `FOV:Cell` gives `FOV` and `Cell`.

A value with more or fewer parts than there are names is not separated: its row gets missing values in the new columns, so that no part ends up in the wrong column. The run summary lists these values.

For example, to separate file names like `Results-ko_01.txt`: `Part` `file name without extension`, `Delimiters` `-_`, and `New columns` `, Treatment, Cell` (the empty first name skips `Results`).

## By a template

Mode `template`: the `Template` describes the layout of the values. `{Name}` is a part that becomes the new column `Name`, `{}` a part that is not kept, and the text between the braces must be in the value as it is. For example, with `Part` `file name without extension`, the template `Results-{FOV}-{Treatment}_{Cell}` takes `FOV` `a`, `Treatment` `ctrl` and `Cell` `1` from `Results-a-ctrl_1.txt`; `{}-{FOV}-{}` takes only `FOV`.

The dialog's example line shows what the template takes from the first row. A value that doesn't fit the template is not separated: its row gets missing values in the new columns, and the run summary lists these values.

## By patterns

Mode `pattern`: each pattern makes one new column: its name, and a regular expression whose first group, in parentheses, is the value. The filename parsers of FLIMAnalyzer 0.6 are presets with such patterns (see [Presets](#presets)). For example, the pattern `/data/(.*?)/` takes `ctrl` from `/data/ctrl/FOV1/cell3.txt`. Backslashes in Windows paths are matched as `/`.

The patterns are a table under `Patterns`, one row per new column: `Column` is the name of the new column, and `Pattern` the regular expression. `Add Pattern` adds a row, and `Remove Patterns` removes the selected rows.

A group that matches nothing gives `?`. A value that the pattern doesn't match gets a missing value. The run summary reports a pattern that matched no value at all.

## Presets

The buttons below the settings load and save presets: settings for how to separate, by name.

* `Load Preset...` fills in the settings of a preset. A preset you saved sets the column, the mode, the part, the delimiters, the new columns' names, the patterns and the template. A built-in preset sets the column, the mode, the part (`value`) and the patterns. The other settings stay as they are.
* `Save as Preset...` saves these settings of the dialog as a preset of your own, in the user settings file (`separate_presets`). A preset with the same name is replaced; the names of the built-in presets can't be used.
* `Remove Presets...` removes presets you saved. The built-in ones can't be removed.

The built-in presets are the filename parsers of FLIMAnalyzer 0.6, as patterns on the `Source` column, named after the categories they take from the file paths. Their patterns match the whole path, so they set `Part` to `value`. The built-in presets are `FOV, Treatment, Cell`, `Treatment, FOV, Cell`, `Treatment, FOV, Time`, `Treatment, Time`, `FOV, Time, Well`, `Compartment, FOV, Treatment, Cell`, `Compartment, Treatment, FOV, Cell` and `Cell line, Compartment, FOV, Treatment, Cell`. For example, `FOV, Treatment, Cell` reads `FOV` `a`, `Treatment` `ctrl` and `Cell` `1` from `Results-a-ctrl-1.txt`, with these patterns:

```
{"name": "FOV", "regex": ".*/.*?[_-](.*?)[_-]"}
{"name": "Treatment", "regex": ".*/.*?[_-].*?[_-](.*?)[_-]"}
{"name": "Cell", "regex": ".*/.*?[_-].*?[_-].*?[_-](\\d*?)\\."}
```

To take categories from the file names in every import, also in [batch mode](/userguide/batch), copy the built-in `Import` workflow (see [Workflow files](/userguide/workflows.md#workflow-files)) and add a step before `Calculate`, for example:

```
{"id": "5", "tool": "Separate Categories", "config": {"column": "Source", "mode": "pattern", "patterns": [ ... ]}}
```

with the patterns of the preset. The ids only need to be unique, so the other steps keep their ids (see [Workflow files](/userguide/workflows.md#workflow-files)).
