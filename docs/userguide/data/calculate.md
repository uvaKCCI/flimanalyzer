# Calculate

The `Calculate` tool adds new columns calculated from others, for example the mean lifetime `NAD(P)H tm` from the amplitudes and lifetimes, or a ratio such as `FLIRR`. The built-in `Import` workflows make the standard FLIM calculations after they read the files (see [Loading Data](/userguide/data/load.md)).

**Menu Access:** `Data` > `Calculate`

1. Select `Data` > `Calculate`.

2. The `Configuration: Calculate` dialog opens with an empty `Calculations` table: a run makes only the calculations you set up in it, not those of earlier runs. Add rows in two ways:

    - `Add Calculations...` lists the calculations that apply to the table: the built-in ones (those of `Import`, such as `FLIRR` and `NAD(P)H tm`) and the ones you saved, marked `(saved)`. A calculation applies if the table has the columns it uses and doesn't have its result yet. Check the ones to add and click `OK`. A calculation that needs another one's result, for example `NADH %`, which needs `NADPH %`, is offered if that one applies too, and is added after it.
    - `Add Row` adds an empty row, a new expression, to fill in (see below).

    `Save as Presets` saves the selected rows, so that `Add Calculations...` offers them in later sessions; `Remove Presets...` removes saved ones. The built-in calculations can't be removed.

    Each row makes one new column:

    - `Use` (default `yes`): `no` leaves the row out.
    - `Column`: the new column's name. If the table already has a column with this name, the new one replaces it; the dialog warns about this.
    - `Kind`: `expression` or `function` (see below). The cells that the row's kind doesn't use are greyed out.
    - `Expression` (kind `expression`): the formula.
    - `Function`, `Arguments` and `Parameters` (kind `function`): the function's name, its argument columns separated by commas, and its parameters as `name=value`, for example `const=3100`.
    - `Keep` (default `yes`): `no` makes a helper column. Later rows can use it, but it is not in the result.
    - `Type` (default `feature`): `category` makes the values categories, for example for a column that groups the rows.
    - `Description`: a note for yourself.

    `Remove Rows` removes the selected rows. The rows are calculated from top to bottom, so a row can use the columns calculated in the rows above it.

    Below the settings, the dialog shows the first calculated value of the first row of the table, for example `Example: NAD(P)H tm = 1240 (and 5 more)`.

3. Click `OK`.

The result is `Table: Calculated`, with the new columns after the existing ones. A row that uses a column the table doesn't have, and that no row above calculates, is skipped. The dialog marks it with a warning, and the run summary lists it. Infinite results, for example from a division by 0, are stored as missing values.

## Expressions

An expression is a formula of columns and numbers: `+`, `-`, `*`, `/`, `**` (power), comparisons (`<`, `<=`, `>`, `>=`, `==`, `!=`), `&` (and), `|` (or), `~` (not), parentheses, and the math functions `abs`, `sqrt`, `exp`, `expm1`, `log` (natural logarithm), `log1p`, `log10`, `sin`, `cos`, `tan`, `arcsin`, `arccos`, `arctan`, `arctan2`, `sinh`, `cosh`, `tanh`, `arcsinh`, `arccosh` and `arctanh`. Type the column names as they are in the table, also with spaces or brackets. For example:

- `NAD(P)H a2[%] / FAD a1[%]`: the FLIRR.
- `log(NAD(P)H tm / FAD tm)`: the logarithm of a ratio.
- `FAD tm > 1000`: `True` or `False` per row; with `Type` `category`, a column to group by.

A name that is not in the table yet, for example a column that a row above calculates, must be in backticks if it has spaces or other characters than letters, digits and `_`: `` `my ratio` * 100 ``. If a name in an expression isn't a column, the dialog marks the row and names the closest column, for example `did you mean 'FAD tm'?`.

Other elements, such as calling methods or functions other than the math functions, are not allowed; the dialog marks such an expression as an error.

## Functions

A function calculates a value from the values of its argument columns, row by row. These are the functions of `Import...`; plugins can add more:

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

The default rows are the calculations of `Import...`: `NAD(P)H tm`, `trp tm` and `FAD tm`, the a2/a1 and a1/a2 ratios, `NADPH %`, `NADH %`, `NADPH/NADH`, the tryptophan FRET efficiencies and distances, `FAD photons/NAD(P)H photons`, `NAD(P)H tm/FAD tm`, `FLIRR` and `NADPH a2/FAD a1`. Rows whose columns are not in the table, for example the tryptophan rows for data without a tryptophan channel, are skipped.
