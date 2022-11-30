# Random Forest Analysis

The `Random Forest Analysis` tool is a machine learning algorithm that deploys several decision trees to ultimately arrive at data feature importance scores. These importance scores tell you how much of an impact that feature has; a higher importance score means that data feature has more impact on the other features.

**Menu Access:** `Analysis` > `Random Forest`

**Toolbar Icon:** ![](/images/analysis/randomforest.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front.
    ![](/images/data/dataframe.png)

2. Start the `Random Forest Analysis` by clicking on the icon in the toolbar or via the `Analysis` > `Random Forest` menu.

3. In the `Configuration: Random Forest Analysis` dialog, define the classifier, n-estimator, and test size.
    - `Classifier`: The categorical column by which the random forest will classify the data by.
    - `N-estimator`: The number of trees used, which will default to 100.
    - `Test Size`: The ratio of testing data to training data, which will default to 0.3. This means that the tool will use 30% test data and 70% training data.
    
    ![](/images/analysis/random_config.png)
    
4. Select the data grouping and data features of interest. Data grouping options are based on the tables category columns,  i.e. `Cell`, `Compartment`, `FOV`, and `Treatment` in this example. Data features correspond to columns with numeric data, `FAD a1`, etc..

  In the example, input data is classified by `Treatment`, and uses the default values for both `N-estimator` and `Test size`. Prior to opening the Random Forest tool, the `Summarize` tool was used to find the mean for FAD a1, FAD a2, FAD chi, NAD(P)H a1, and NAD(P)H a2, grouped by 'Cell, FOV, Treatment`. This explains why only those data features appear in the configuration box.
  
4. Click `OK`.

5. The analysis results are shown in a new data table containing the importance scores for each of the selected data features, and also produces a histogram of this information, if the `Importance Histogram` checkbox is checked off. As shown in the example importance histogram, an accuracy value is produced as well, with higher accuracy values being better.

## Example Output

**Example Results:** 

Importance Histogram using the configuration settings shown before:

![](/images/analysis/random_result1.png)

New data table showing each data feature's importance score:

![](/images/analysis/random_result2.png)

In this example, NAD(P)H a1 had the highest importance score by a decent margin, meaning that it was more impactful in the generated decisions trees than the other selected features.

