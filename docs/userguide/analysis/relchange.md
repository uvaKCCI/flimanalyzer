# Relative Change Analysis

The `Relative Change` analysis tool converts input data to fold-change values relative to mean/median of reference group. This can be used to create data plots that depict trends relative to a specific reference group and value.

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front.
    ![](/images/data/dataframe.png)

2. Start the Relative Change tool by clicking on the icon in the toolbar or via the `Analysis` > `Relative Change` menu.

3. In the `Configuration: Relative Change` dialog, define the reference group, value and normalization method.
    - `Reference Group`: The categorical column containing the **Reference Value** to normalize to.
    - `Reference Value`: The value in the selected **Reference Group** to normalize to.
    - `Method`: Either **mean** or **median** for each data group.
    
    ![](/images/analysis/relchange-config-grouping.png)

4. Select the data grouping and data features of interest. Data grouping options are based on the tables category columns,  i.e. `Cell`, `Compartment`, `FOV`, and `Treatment` in this example. Data features correspond to columns with numeric data, `FAD a1`, etc..

    In the example, input data is grouped by `Treatment` (implicit as specified **Reference Group**) and `FOV`.  For each data group and data feature, the **mean** value of the `Treatment:Ctrl` group is calculated, aka the mean reference values. Each row value is then expressed as fold-change relative to its group's and data features' mean reference values.

4. Click `OK`.

5. The analysis results are shown in new data table, with each row representing one particular data group and aggregated numbers shown in individual columns.

## Example Output

**Example Results:** `Data Grouping` - Treatment, FOV
![](/images/analysis/relchange-result-grouping.png)
    
```{note}
You can confirm the conversion by running a [Summary Table Analysis](/userguide/analysis/summarystats) on the **Relative-mean** (or **Relative-median**) table using the same data grouping, i.e `Treatment, FOV` for this example. The mean (or median) for each `Treatment:Ctrl` group should equal 1.0.
```
