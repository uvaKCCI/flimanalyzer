# Random Forest Analysis

The `Random Forest Analysis` tool is a machine learning algorithm that deploys decision trees to arrive at data feature importance scores. These scores measure each feature's impact on the predictive behavior of the model, with higher scores indicating a higher impact.

**Menu Access:** `Analysis` > `Random Forest`

**Toolbar Icon:** ![](/images/analysis/randomforest.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This will bring the selected table window to the front.
    ![](/images/analysis/rf-start.png)


2. Start the `Random Forest Analysis` by clicking on the icon in the toolbar or via the `Analysis` > `Random Forest` menu.

3. In the `Configuration: Random Forest Analysis` dialog, define the classifier, n-estimator, and test size.
    - `Classifier`: One of the categorical columns. It defines what you want to "predict." Using `Treatment` as a classifier, for example, will create a model that will determine which data features are most important in predicting a data point's treatment.
    - `N-estimator`: The number of trees used, which will default to 100.
    - `Test Size`: The ratio of testing data to training data, which will default to 0.3. This means that the tool will use 30% test data and 70% training data.
    
    
    ![](/images/analysis/rf-config.png)
    
    
4. Select the data grouping and data features of interest. Data grouping options are based on the tables category columns,  i.e. `Cell`, `FOV`, and `Treatment` in this example. Data features correspond to columns with numeric data, `FAD a1`, etc..

  In the example, input data is classified by `Treatment`, and uses the default values for both `N-estimator` and `Test size`. 
  
4. Click `OK`.


5. The analysis results are shown in a new data table containing the importance scores for each of the selected data features, and also produces a histogram of this information, if the `Importance Histogram` checkbox is checked off. As shown in the example importance histogram, an accuracy value is produced as well, with higher accuracy values being better.

## Example Output

**Example Results:** 

Importance Histogram using the configuration settings shown before:

![](/images/analysis/rf-output1.png)

New data table showing each data feature's importance score:

![](/images/analysis/rf-output2.png.png)

In this example, FAD a1 had the highest importance score, meaning that it was more impactful in predicting the treatment of a particular cell. There is likely large variation in FAD a1 values across the various treatments.

