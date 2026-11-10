# Filter Tool

The `Filter` tool creates a new table with only the rows you want to keep: rows with selected category values, rows whose values lie within set ranges, and rows for which a condition is true.

**Menu Access:** `Data` > `Filter`

**Tool panel icon:** ![](/images/data/filter.png)

The filters of the table window (see [Filtering Data](filter.md)) only hide rows in that window. The `Filter` tool instead creates a new table, `Table: Filtered`, and leaves the original table unchanged. Use it when the filtered rows should be saved, or used as the input of other tools and workflows.

The range filters are the same as those of the table windows: a range you change in a table window's `Filter Settings` shows in the `Filter` dialog, and the other way round. The table windows' `Filter Data` switch does not affect the `Filter` tool, which always applies the filters checked in its dialog.

## Filtering the Data

1. Open a data table, then start `Filter` from the menu or the tool panel.

2. Under `Category values to keep`, select a category column in the list on the left. Its values appear on the right, all checked. Uncheck the values whose rows should be dropped. Columns that filter rows are marked with `*`; columns you don't change keep all their rows.

3. Under `Range filters`, check `Use` for the columns to filter and set their limits:
    - `Low` and `High`: rows with a value below `Low` or above `High` are dropped. Rows with a value equal to a limit are kept. Leave a limit empty for no limit on that side.
    - `Drop missing` (checked by default): also drops rows that have no value in the column.

    `Low` can't be larger than `High`; the dialog marks such a row.

    ![](/images/data/filtertool-config.png)

4. Under `Other filters`, add conditions and further filters, one per row (`Add Row`, `Remove Rows`):
    - `Use`: `no` switches the filter off.
    - `Kind`: `expression` (the default for a new row), `range` or `category`. The cells the row's kind doesn't use are greyed out.
    - `Expression`: a condition, written as in the [Calculate](calculate.md#expressions) tool, for example `` `FAD tm` > 1000 & `FAD a1[%]` < 90 ``. Use `&` for and, `|` for or, and `~` for not. Rows with a missing value in a column of the condition are dropped.
    - `Column`, `Low`, `High`, `Drop missing` and `Values to keep`: a further range or category filter, for example a second range on a column that has one under `Range filters`. Separate the values to keep with commas.

    Groups of filters (see [Filters in settings files](#filters-in-settings-files)) are listed here too. Their `Use` can be changed, the filters in them only in the settings file.

5. Click `OK`. The new table `Table: Filtered` opens in its own window.

A row is kept only if it passes every filter that is switched on: its category values are among the selected ones, its values lie within all checked ranges, and every condition is true for it. A filter on a column that the table doesn't have keeps all rows; the dialog marks it with a warning. The log file lists how many rows each filter dropped.

## Filters in settings files

In the settings (see [Settings](/userguide/settings)), the filters are the `Filter` tool's `filters`: a list of filters, each with a `kind`. A row is kept if every filter of the list keeps it:

```
"Filter": {"config": {"filters": [
  {"kind": "range", "column": "FAD t1", "low": 10, "high": 1500, "dropna": true, "enabled": true},
  {"kind": "category", "column": "Treatment", "keep": ["ctrl", "Dox15"]},
  {"kind": "expression", "expression": "`FAD tm` > 1000"},
  {"kind": "any", "filters": [
    {"kind": "range", "column": "FLIRR", "high": 0.5},
    {"kind": "category", "column": "FOV", "keep": ["1"]}
  ]}
]}}
```

* `range`, `category` and `expression`: the filters described above. An empty `low` or `high` (`null`) is no limit.
* `all`, `any` and `not`: groups, with their own `filters`. `all` keeps the rows that all of its filters keep, `any` the rows that at least one of them keeps, and `not` the rows that `all` would drop. Groups can contain groups. An empty group keeps all rows.
* `enabled` (default `true`): `false` switches a filter or a whole group off; it then keeps all rows.
