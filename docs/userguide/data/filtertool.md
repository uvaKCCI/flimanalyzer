# Filter Tool

The `Filter` tool creates a new table with only the rows you want to keep: rows with selected category values, rows whose values lie within set ranges, and rows for which a condition is true.

**Menu Access:** `Data` > `Filter`

**Tool panel icon:** ![](/images/data/filter.png)

The filters of the table window (see [Filtering Data](filter.md)) only hide rows in that window. The `Filter` tool instead creates a new table, `Table: Filtered`, and leaves the original table unchanged. Use it when the filtered rows should be saved, or used as the input of other tools and workflows.

The feature filters of the `Filter` tool are the defaults for new table windows (see [Filtering Data](filter.md#presets)): a new table window starts with the ranges that are checked here. A change in a table window's `Filter Features...` changes only that window. The `Filter` tool applies the filters checked in its dialog to the rows the table window shows. If the window's `Filter Features` or `Filter Categories` is checked, the rows that these filters hide are not in the tool's input. This is the same for every tool started for that window.

## Filtering the Data

The dialog shows `Use filters`, the switch of all filters, and then the filters in three filter components: feature, category and other filters. Each filter component has its own switch. While a filter component's switch or `Use filters` is off, the filter component is greyed out.

1. Open a data table, then start `Filter` from the menu or the tool panel.

2. Under `Feature filters` (switch: `Use feature filters`), each row is a column of the table with numeric values (`Feature`). Today the feature filters are range filters. Check `Use` for the columns to filter and set their limits:
    - `Low` and `High`: rows with a value below `Low` or above `High` are dropped. Rows with a value equal to a limit are kept. Leave a limit empty for no limit on that side.
    - `Drop missing` (checked by default): also drops rows that have no value in the column.

    `Low` can't be larger than `High`; the dialog marks such a row. Each column has one range filter here; put a second range on a column under `Other filters`.

    `Select All` and `Deselect All` check or uncheck `Use` for all columns. `Load Feature Settings...` and `Save Feature Settings...` load and save the limits of each column (see [Settings](/userguide/settings)).

    ![](/images/data/filtertool-config.png)

3. Under `Category values to keep` (switch: `Use category filters`), select a category column in the list on the left. Its values appear on the right, all checked. Uncheck the values whose rows should be dropped. Columns that filter rows are marked with `*`; columns you don't change keep all their rows. A column whose filter is off in the settings is marked with `* (off)`; when you check or uncheck one of its values, its filter is on again.

4. Under `Other filters` (switch: `Use other filters`), add conditions and further filters, one per row (`Add Other filter`, `Remove Other filters`):
    - `Use`: `no` switches the filter off.
    - `Kind`: `range` (the default for a new row), `category` or `expression`. The cells the row's kind doesn't use are greyed out.
    - `Expression`: a condition, written as in the [Calculate](/userguide/analysis/calculate.md#expressions) tool, for example `` `FAD tm` > 1000 & `FAD a1[%]` < 90 ``. Use `&` for and, `|` for or, and `~` for not. Rows with a missing value in a column of the condition are dropped.
    - `Column`, `Low`, `High`, `Drop missing` and `Values to keep`: a further range or category filter, for example a second range on a column that has one under `Feature filters`. Separate the values to keep with commas.

    Groups of filters (see [Filters in settings files](#filters-in-settings-files)) are listed here too. Their `Use` can be changed, the filters in them only in the settings file.

5. Click `OK`. The new table `Table: Filtered` opens in its own window.

**Use filters:** the switch of all filters (`enabled` in settings files, on by default). If it is off, the tool keeps all rows. A table window has no such switch: it has `Filter Features` for its feature filters and `Filter Categories` for its hidden category values.

**Presets:** the buttons below the settings load and save `Use filters` and the three filter components by name. `Load Preset...` replaces them with those of a preset. A preset saved in a table window's `Filter Features...` has only the feature filters and their switch: it replaces only the feature filters and `Use feature filters`. `Save as Preset...` saves them as a preset; a preset with the same name is replaced. If the settings are not valid, a message shows the problems and no preset is saved. `Remove Presets...` removes presets. Saving or removing a preset changes only that preset. The presets are in the user settings file. A table window's `Filter Features...` offers them too; it uses only their feature filters.

A row is kept only if every filter component keeps it: its values lie within all checked ranges, its category values are among the selected ones, and every other filter keeps it. A filter on a column that the table does not have is not used. The feature and category filter components list only the table's columns, and keep such a filter unchanged in the settings. Under `Other filters`, its row is marked with a warning. A filter that is not used drops no rows, and a group combines only the filters it uses. The log file lists how many rows each filter dropped.

## Filters in settings files

In the settings (see [Settings](/userguide/settings)), the `Filter` tool's settings have the switch of all filters, `enabled`, and three filter components. Each filter component has its own `enabled` and its `filters`, a list of filters, each with a `kind`:

```
"Filter": {"config": {
  "enabled": true,
  "features": {"enabled": true, "filters": [
    {"kind": "range", "column": "FAD t1", "low": 10, "high": 1500, "dropna": true, "enabled": true}
  ]},
  "categories": {"enabled": true, "filters": [
    {"kind": "category", "column": "Treatment", "keep": ["ctrl", "Dox15"]}
  ]},
  "other": {"enabled": true, "filters": [
    {"kind": "expression", "expression": "`FAD tm` > 1000"},
    {"kind": "any", "filters": [
      {"kind": "range", "column": "FLIRR", "high": 0.5},
      {"kind": "category", "column": "FOV", "keep": ["1"]}
    ]}
  ]}
}}
```

* `features` (`Feature filters`): the feature filters, one per column. Today these are `range` filters.
* `categories` (`Category values to keep`): `category` filters only, one per column.
* `other` (`Other filters`): filters of all kinds, for example a second range on a column, conditions and groups.
* `range`, `category` and `expression`: the filters described above. An empty `low` or `high` (`null`) is no limit.
* `all`, `any` and `not`: groups, with their own `filters`. `all` keeps the rows that all of its filters keep, `any` the rows that at least one of them keeps, and `not` the rows that `all` would drop. Groups can contain groups. A group combines only the filters it uses; a filter that is off or on a column the table does not have is not used. A group that uses none of its filters is not used itself: it drops no rows. For example, an `any` group with one filter on a missing column and one that keeps half the rows keeps that half, and a `not` group with only filters that are off drops no rows.
* `enabled` (default `true`): `false` switches a filter, a whole group or a whole filter component off; it is then not used and drops no rows. The top-level `enabled` is `Use filters`, the switch of all filters.

A row is kept if every filter component keeps it, and a filter component keeps a row if every filter of its list that is used keeps it. Two range or category filters on the same column in `features` or `categories` are not valid; put the second one in `other`.

A filter applies only if every `enabled` on its way is `true`: the top-level `enabled` (`Use filters`), that of its filter component, that of each group that contains the filter, and its own. The `enabled` values are combined with a logical AND. For example, a range filter with `"enabled": true` in a group with `"enabled": false` is not used.

Settings of FLIMAnalyzer 0.6 are converted when they are read: range filters go to `features` (the feature filters), category filters to `categories`. A second filter on a column goes to `other`, so that no filter is lost.
