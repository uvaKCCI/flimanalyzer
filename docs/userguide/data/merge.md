# Merge Data

The `Merge Data` tool merges two data tables based on shared category columns values.

**Menu Access:** `Analysis` > `Merge Data`

**Toolbar Icon:** ![](/images/analysis/merge.png)

The `Merge Data` tool takes one data table's values and inserts it into another table in accordance with shared categorical column values. For instance, a row from one table with the `Cell, FOV, Treatment` identifier `01, a, ctrl`, will have its data feature values merged onto rows sharing that same identifier on another table.

To use the `Merge Data` tool, follow the steps below:
  1. You first need to have two data tables open to complete a merge. In the example below, the table on top is the master file with all the raw data values, while the one below contains only the FAD a1 mean for each `Cell, FOV, Treatment` grouping. This was done using the `Summarize` tool.

  Master file:
  ![](/images/data/merge-start.png)
  
  Summarized data, with the mean for FAD a1 taken for each `Cell, FOV, Treatment` identifier:
  ![](/images/data/merge-summary.png)
  
  2. Open the `Merge Data` tool either from menu or toolbar icon. In the `Configuration: Merge Data` dialog, select the two tables you would like to merge. The dropdown menu in between the two table selections provides options on how you would like to merge them. In this instance, `Merge Left` is selected, meaning that the table on the right will be merged into the table on the left. If this is not the desired output, the merging options can be altered using that dropdown menu.
  
  ![](/images/data/merge-dialog.png)
  
  3. Click `OK`.
  4. A new merged table is formed, as directed in the configuration of the tool. In the example merged table below, the FAD a1 mean value is now inserted into the master file based on the shared categorical column values between them. 

  ![](/images/data/merge-res1.png) ![](/images/data/merge-res3.png)
  
  For each `Cell, FOV, Treatment` identifier, the corresponding FAD a1 mean value is inputted.
