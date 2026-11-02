# Frequency Histogram

The `Frequency Histogram` tool creates frequency histograms for grouped data.

**Menu Access:** `Plot` > `Frequency Histogram`

**Toolbar Icon:** ![](/images/analysis/histogram.png)

## Creating the Plot

1. Go to the `Window` menu and select one of the data tables. The table window comes to the front.
    ![](/images/data/dataframe.png)

2. Start the Frequency Histogram tool by clicking on its icon in the tool panel or via the `Plot` > `Frequency Histogram` menu.

3. In the `Configuration: Frequency Histogram` dialog, select the grouping, the features to plot and how the histogram looks. You can group the data by the table's category columns, here `Treatment`, `FOV` and `Cell`. The features are the columns with numbers, such as `FAD a1`. The `Style` menu offers four histogram styles: `bar`, `barstacked`, `step` and `stepfilled`. The `Stacked` and `Cumulative` checkboxes change how the data is shown. `Binned data table` also creates a table with the counts in each bin of the histogram.

    The features are listed in a table, with a row for each numeric column. Check `Use` to plot a feature, and set its `Min`, `Max` and `Bins` in the same row. If you leave `Min` or `Max` empty, the smallest or largest value in the data is used. `Auto min/max range` uses each feature's smallest and largest value in the data, and ignores the `Min` and `Max` in the table. `Same bins for all` gives all features the same number of bins. `Load Feature Settings...` and `Save Feature Settings...` load and save the ranges and bins (see [Settings](/userguide/settings)).

    In the example, `FAD a1[%]` is plotted from 50 to 90 with 40 bins, grouped by `Treatment`, in the `bar` style, with `Binned data table` checked.

    ![](/images/analysis/histogram-config.png)

4. Click `OK`.

5. Each selected feature is plotted in its own plot window.

## Example Output

**Example Results:** Use of the `bar` histogram style:

![](/images/analysis/histogram-results1.png)

**Example Results:** Use of the `barstacked` histogram style:

![](/images/analysis/histogram-results2.png)

**Example Results:** Use of the `step` histogram style:

![](/images/analysis/histogram-results3.png)

**Example Results:** Use of the `stepfilled` histogram style:

![](/images/analysis/histogram-results4.png)

**Example Results:** Generated `Binned data table`:

![](/images/analysis/histogram-results1a.png)

```{note}
You can change and save plots as described in the [Plots](/userguide/plots/index) section.
```
