# Calculate

The `Calculate` tool adds new columns calculated from others, for example the mean lifetime `NAD(P)H tm` from the amplitudes and lifetimes, or a ratio such as `FLIRR`. The built-in `Import` workflow makes the standard FLIM calculations on the tables read from the files (see [Import Tables](/userguide/data/load.md#import-tables)).

**Menu Access:** `Analysis` > `Calculate`

**Tool panel icon:** ![](/images/analysis/calculate.png)

1. Select `Analysis` > `Calculate`.

2. The `Configuration: Calculate` dialog opens with an empty `Calculations` list: a run makes only the calculations you set up in it, not those of earlier runs. The list shows each calculation's new column, what it computes and its options; it isn't edited directly. Use the buttons below it:

    - `Add Calculation...` opens the calculation editor (see below); `OK` there adds the calculation to the list. `Edit...` (or a double click on a row) opens it for the selected calculation.
    - `Remove` removes the selected calculations; `Up` and `Down` move the selected one. The calculations are made from top to bottom, so a calculation can use the columns of those above it.
    - `Load Preset...` lists the calculations that apply to the table: the built-in ones (those of `Import`, such as `FLIRR` and `NAD(P)H tm`) and the ones you saved, marked `(saved)`. A calculation applies if the table has the columns it uses and doesn't have its result yet. Check the ones to add and click `OK`. A calculation that needs another one's result, for example `NADH %`, which needs `NADPH %`, is offered if that one applies too, and is added after it. If you check only `NADH %`, `Load Preset...` adds `NADPH %` too, before it.
    - `Save as Preset...` saves the selected calculations, so that `Load Preset...` offers them in later sessions. A saved calculation with the same new column name is replaced; `Remove Presets...` removes saved ones. The built-in calculations can't be removed.

    **The calculation editor** first asks for the `Kind`, `expression` or `function`. Below it are the fields of every kind, which stay in place when you change the kind:

    - `Use` (default checked): unchecked, the calculation is left out.
    - `New Column`: the new column's name. If the table already has a column with this name, the new one replaces it; the dialog warns about this.
    - `Keep` (default checked): unchecked makes a helper column. Later calculations can use it, but it is not in the result.
    - `Description`: a note for yourself.

    Below them are the fields of the kind:

    - `Expression` (kind `expression`): the formula (see [Expressions](#expressions)).
    - `Function` (kind `function`): one of the functions (see [Functions](#functions)); `Arguments`: the table's features it takes, checked and in the function's order (use the arrows to move them); `Parameters`: the function's own parameters, with their defaults, for example `const` = 3100 for `trp_Eperc_1`. A function without parameters shows `(none)`. Above the arguments, a preview shows the calculation as a call, for example `FAD tm = tm(FAD a1[%], FAD t1, FAD a2[%], FAD t2)`, and the function's parameters and what it does, for example `tm(a1perc, t1, a2perc, t2): Return the mean lifetime of two components, weighted by their amplitudes.`, so you can check that each feature is in the right place.

    Below the fields, the editor shows the result for the table's first rows in a small table: the columns the calculation uses, and the calculated column, marked `→`, for example `→ FLIRR`. Otherwise it shows what is wrong, for example `skipped: 'FAD tn' (did you mean 'FAD tm'?) not in the table or calculated before`. `OK` is enabled only when the calculation can be made on the table.

3. Click `OK`.

The result is `Table: Calculated`, with the new columns after the existing ones. A row that uses a column the table doesn't have, and that no row above calculates, is skipped. The dialog marks it with a warning, and the run summary lists it. Infinite results, for example from a division by 0, are stored as missing values. A calculation whose results are numbers makes a feature; one whose results are `True` or `False`, or text, makes a category column.

## Expressions

An expression is a formula of columns and numbers: `+`, `-`, `*`, `/`, `//` (division rounded down), `%` (remainder), `**` (power), comparisons (`<`, `<=`, `>`, `>=`, `==`, `!=`), `&` (and), `|` (or), `~` (not), also written `and`, `or` and `not`, parentheses, and the math functions `abs`, `sqrt`, `exp`, `expm1`, `log` (natural logarithm), `log1p`, `log10`, `sin`, `cos`, `tan`, `arcsin`, `arccos`, `arctan`, `arctan2`, `sinh`, `cosh`, `tanh`, `arcsinh`, `arccosh` and `arctanh`. Type the column names as they are in the table, also with spaces or brackets. For example:

- `NAD(P)H a2[%] / FAD a1[%]`: the FLIRR.
- `log(NAD(P)H tm / FAD tm)`: the logarithm of a ratio.
- `FAD tm > 1000`: `True` or `False` per row, a category column to group by.

A name that is not in the table yet, for example a column that a row above calculates, must be in backticks if it has spaces or other characters than letters, digits and `_`: `` `my ratio` * 100 ``. If a name in an expression isn't a column, the dialog marks the row and names the closest column, for example `did you mean 'FAD tm'?`.

Other elements, such as calling methods or functions other than the math functions, are not allowed; the dialog marks such an expression as an error.

## Functions

A function calculates a value from the values of its argument columns, row by row. These are the functions the built-in `Import` workflow uses; plugins can add more:

| Function | Arguments | Parameters | Result |
|:--|:--|:--|:--|
| `tm` | a1[%], t1, a2[%], t2 | | the mean lifetime, (a1[%] × t1 + a2[%] × t2) / 100 |
| `ratio` | v1, v2 | | v1 / v2; missing if v2 is 0 |
| `nadph_perc` | NAD(P)H t2 | | the NADPH share in %, from t2 |
| `nadh_perc` | NADPH % | | 100 − NADPH % |
| `trp_Eperc_1` | trp tm | `const` (default 3100) | the FRET efficiency in %, (1 − tm / const) × 100 |
| `trp_Eperc_2` | trp t1, trp t2 | | (1 − t1 / t2) × 100 |
| `trp_Eperc_3` | trp t1 | `const` (default 3100) | (1 − t1 / const) × 100 |
| `trp_r` | trp E% | | the distance, 2.1 × (100 / E% − 1)^(1/6); missing for E% outside 0 to 100 |

The built-in presets of `Load Preset...` are the calculations of the built-in `Import` workflow: `NAD(P)H tm`, `trp tm` and `FAD tm`, the a2/a1 and a1/a2 ratios, `NADPH %`, `NADH %`, `NADPH/NADH`, the tryptophan FRET efficiencies and distances, `FAD photons/NAD(P)H photons`, `NAD(P)H tm/FAD tm`, `FLIRR` and `NADPH a2/FAD a1`. The dialog opens with an empty `Calculations` list; `Load Presets...` adds these calculations. It offers only those whose columns are in the table, so for data without a tryptophan channel, for example, the tryptophan calculations are not offered.
