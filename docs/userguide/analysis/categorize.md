# Categorize Data

The `Categorize Data` tool defines thresholded value bins for a selected data table column to create a new category column with custom bin labels.

**Menu Access:** `Analysis` > `Categorize Data`

**Toolbar Icon:** ![](/images/analysis/categorize.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front.
    ![](/images/data/dataframe.png)

2. Start the Categorization tool by clicking on the icon in the toolbar or via the `Analysis` > `Categorize Data` menu.

3. In the `Configuration: Categorize Data` dialog, fill in the following parameters:

    * **Category:** Header for new category column.
    * **Feature to categorize:** Data column to use for thresholded value bins.
    * **Category bins:** Comma-separated list of threshold values used to define bins.
    * **Category labels:** Comma-separated list of descriptors used for bins. Number of descriptors is one less than the number of threshold values.
    * **Default:** Default label used for data values that fall outside of the defined threshold bins.
    * **Merge input:** Copy all data columns from input table into new table. 

    ![](/images/analysis/categorize-config.png)

    In the shown example, we specify 4 threshold values to define 3 bins:
    
    * **low:** -100000.0 < x <= 50.0
    * **medium:** 50.0 < x <= 75.0
    * **high:** 75.0 < x <= 100000.0
    
    For values x <= -100000 (smallest threshold) or x > 100000 (largest threshold) the `Default` category value will be used ("unassigned" in this example). 

4. Click `OK`.

5. The new category labels will be shown as a new column in a new table along with all the other category columns present in the input table.

## Example Output

**Example Results:**

![](/images/analysis/categorize-results.png)
