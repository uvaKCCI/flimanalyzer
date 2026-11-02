# FLIRR Plot

The `FLIRR Plot` tool shows FLIRR (Fluorescence Lifetime Imaging Redox Ratio) trends in one figure. The figure contains:
- a scatter plot of `FAD a1[%]` against `NAD(P)H a2[%]`,
- KDE plots of `FAD a1[%]`, `NAD(P)H a2[%]` and FLIRR,
- a line plot of FLIRR along the first grouping column,
- a bar plot of the mean FLIRR of each group.

**Menu Access:** `Plot` > `FLIRR Plot`

**Toolbar Icon:** ![](/images/analysis/flirrplot.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/analysis/flirr_data.png)

2. Start the FLIRR Plot tool by clicking on its icon in the tool panel or via the `Plot` > `FLIRR Plot` menu.

3. In the `Configuration: FLIRR Plot` dialog, select the grouping. The first grouping column sets the colors of the points, curves and bars. It is also the x axis of the line plot. If you add a second grouping column, the line plot gets one line for each of its values, each with its own line style. The second column also groups the bars.

    `FLIRR`, `FAD a1 %` and `NAD(P)H a2 %` select the columns to plot. If you leave them empty, the tool finds the columns by name:
    - `FLIRR`: the column whose name contains `FLIRR`.
    - `FAD a1 %`: the column whose name contains `FAD`, `a1` and `%`.
    - `NAD(P)H a2 %`: the column whose name contains `NAD`, `a2` and `%`.

    If a column is not found, the dialog marks the field. Choose the column there.

    ![](/images/analysis/flirr-config.png)

4. Click `OK`.

5. The plots appear together in a new plot window.

## Example Output

**Example Results:** FLIRR Plot of the data grouped by `Treatment` and `FOV`

![](/images/analysis/flirr-result.png)

```{note}
You can change and save plots as described in the [Plots](/userguide/plots/index) section.
```
