# Random Forest

The `Random Forest` tool trains a random forest to predict a category from the features. A random forest is a large set of decision trees whose answers are combined. The tool reports how much each feature contributes to the prediction, and how accurate the prediction is on test data.

**Menu Access:** `Analysis` > `Random Forest`

**Toolbar Icon:** ![](/images/analysis/randomforest.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front.
    ![](/images/analysis/rf-start.png)

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Random Forest` menu.

3. In the `Configuration: Random Forest` dialog, set:
    - `Predict`: the category column to predict. With `Treatment`, the model shows which features are most important for telling the treatments apart.
    - `Trees`: the number of trees (default 100).
    - `Test fraction`: the fraction of the rows that are kept aside to test the accuracy (default 0.3: 30% test data, 70% training data).
    - `Importance plot`: a bar plot of the importance scores, labeled with the accuracy.
    - `Random seed`: with a number, every run gives the same results.

4. Select the features. In the example, the amplitudes and lifetimes of FAD and NAD(P)H, and FLIRR, are used to predict `Treatment`, with the default number of trees and test fraction.

    ![](/images/analysis/rf-config.png)

5. Click `OK`.

6. The results are shown in a new data table with the importance score of each feature, highest first. If `Importance plot` is checked, the plot is shown as well.

## Example Output

The importance plot, with the accuracy on the test data:

![](/images/analysis/rf-output.png)

The importance scores:

![](/images/analysis/rf-output2.png)

In this example, `FLIRR` has the highest importance score: it is the feature that contributes most to predicting the treatment.
