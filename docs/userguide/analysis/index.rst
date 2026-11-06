Analysis
========

`Summarize`, `Relative Change` and `KS-Statistics` can group the data by the values of category columns and analyze each group separately. You can group by one category column or by a combination of several. `Autoencoder: Train` uses the grouping to split the data into training and validation sets, and `Autoencoder: Augment Data` to number the copies' cells. `Series Analysis` and `Random Forest` show a `Grouping` setting, but it has no effect. The other analysis tools have no grouping. Category column headers have a light blue background. All other column headers are gray.

.. image:: /images/data/dataframe.png

The example table has these category columns that you can use for grouping: `Cell, Compartment, FOV, Treatment`. When you group by several category columns, you can choose their order (the grouping hierarchy).

.. note::
    The order of the grouping columns changes the order of the rows in the result tables and how the data is arranged in plots. The effect differs from tool to tool. Each tool's page shows it with examples.

.. list-table::
   :widths: 10 10 30
   :header-rows: 1

   * - Icon
     - Analysis Tool
     - Description
   * - .. image:: /images/analysis/summary.png 
     - `Summarize <summary.html>`_
     - Calculates the count, minimum, maximum, mean, median, standard deviation, standard error of the mean, 25th and 75th percentiles, and sum of grouped data.
   * - .. image:: /images/analysis/relchange.png 
     - `Relative Change <relchange.html>`_
     - Converts the data to fold-change values, relative to the mean or median of a reference group.
   * - .. image:: /images/analysis/seriesanalysis.png 
     - `Series Analysis <seriesanalysis.html>`_
     - Analyzes a series of values spread across several table columns.
   * - .. image:: /images/analysis/categorize.png 
     - `Categorize Data <categorize.html>`_
     - Adds a category column based on value ranges of a feature.
   * - .. image:: /images/analysis/randomforest.png 
     - `Random Forest <randomforest.html>`_
     - Predicts a category from the features with a random forest, and shows which features matter most.
   * - .. image:: /images/analysis/pca.png 
     - `PCA <pca.html>`_
     - Principal component analysis: summarizes many features in a few new columns (principal components) and outputs their values.
   * - .. image:: /images/analysis/kmeans.png 
     - `K-Means <kmeans.html>`_
     - Groups similar data points into clusters.
   * - .. image:: /images/analysis/gmm.png
     - `Gaussian Mixed Model <gmm.html>`_
     - Groups data points into clusters, each described by a Gaussian (bell-shaped) distribution, and gives each point's probability of belonging to each cluster.
   * - .. image:: /images/analysis/ks.png 
     - `KS-Statistics <ks.html>`_
     - Compares the distributions of a feature between the groups of a category column, two at a time, with the Kolmogorov–Smirnov test.
   * - .. image:: /images/analysis/aetrain.png 
     - `Autoencoder: Train <aetrain.html>`_
     - Trains an autoencoder model on selected data features. 
   * - .. image:: /images/analysis/aerun.png 
     - `Autoencoder: Run <aerun.html>`_
     - Applies a pre-trained autoencoder model to data.
   * - .. image:: /images/analysis/aeaugment.png 
     - `Autoencoder: Augment Data <aeaugment.html>`_
     - Generates augmented data with a pre-trained autoencoder model.

.. toctree::
    :maxdepth: 2
    :hidden:
    :glob:
    
    summary
    relchange
    seriesanalysis
    categorize
    randomforest
    pca
    kmeans
    gmm
    ks
    aetrain
    aerun
    aeaugment


