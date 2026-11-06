# FLIRR Plot

The `FLIRR Plot` tool shows FLIRR (Fluorescence Lifetime Imaging Redox Ratio) trends in one figure. The figure contains:
- a scatter plot of `FAD a1[%]` against `NAD(P)H a2[%]`,
- KDE plots of `FAD a1[%]`, `NAD(P)H a2[%]` and FLIRR,
- a line plot of the mean FLIRR along the first grouping column,
- a bar plot of the mean FLIRR of each group, with the standard error of the mean (S.E.M.) as error bars on the upper side of the bars.

**Menu Access:** `Plot` > `FLIRR Plot`

**Tool panel icon:** ![](/images/analysis/flirrplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/analysis/flirr_data.png)

2. Start the FLIRR Plot tool by clicking on its icon in the tool panel or via the `Plot` > `FLIRR Plot` menu.

3. In the `Configuration: FLIRR Plot` dialog, select the grouping. At least one grouping column is needed. The grouping columns have these roles:
    - Scatter plot and KDE plots: the 1st grouping column sets the colors of the points and curves. The other grouping columns are not used.
    - Line plot: the 1st grouping column is the x axis. With a 2nd grouping column, the line plot has one line for each of its values, each with its own line style. Further grouping columns are not used.
    - Bar plot: with one grouping column, there is one bar for each of its values, all in the same color. With 2 or more, the 1st grouping column sets the colors of the bars, and the other columns set the bar positions along the x axis, as in the [Bar Plot](/userguide/plots/barplot).

    `FLIRR`, `FAD a1 %` and `NAD(P)H a2 %` select the columns to plot. If you leave them empty, the tool takes the first column with numbers whose name fits:
    - `FLIRR`: the name contains `FLIRR`, in upper or lower case.
    - `FAD a1 %`: the name contains `FAD`, `a1` and `%`, and neither `FLIRR` nor `/`.
    - `NAD(P)H a2 %`: the name contains `NAD`, `a2` and `%`, and neither `FLIRR` nor `/`.

    If a column is not found, the dialog marks the field. Choose the column there.

    The FLIRR Plot has no `Legend` setting. The scatter plot and the line plot show their own legends.

    ![](/images/analysis/flirr-config.png)

4. Click `OK`.

5. The plots appear together in a new plot window, named after the grouping, for example `Plot: FLIRR Plot: ['Treatment', 'FOV']`.

## Example Output

**Example Results:** FLIRR Plot of the data grouped by `Treatment` and `FOV`

![](/images/analysis/flirr-result.png)

```{note}
You can zoom into the plots, change their axes, labels and line colors, and save the figure in its plot window. See [The Plot Window](/userguide/plots/plotwindow).
```
