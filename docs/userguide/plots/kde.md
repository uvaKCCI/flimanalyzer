# KDE Plots

The `KDE` tool creates kernel density estimate (KDE) plots of grouped data. A KDE plot shows the distribution of a feature as a smooth curve, like a smoothed histogram.

**Menu Access:** `Plot` > `KDE`

**Toolbar Icon:** ![](/images/analysis/kde.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the KDE tool by clicking on its icon in the tool panel or via the `Plot` > `KDE` menu.

3. In the `Configuration: KDE` dialog, select the grouping and the features to plot. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`.

    In the example, `FLIRR` is plotted, grouped by `Treatment` and `FOV`.

    ![](/images/analysis/kde-config.png)

4. Click `OK`.

5. Each selected feature is plotted in its own plot window.


## Example Output

**Example Results:** `Grouping` - Treatment, FOV

![](/images/analysis/kde-results.png)

```{note}
You can change and save plots as described in the [Plots](/userguide/plots/index) section.
```
