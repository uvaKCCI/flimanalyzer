Analysis
========

`Summarize`, `Relative Change` and `KS-Statistics` can group the data by the values of category columns and analyze each group separately. You can group by one category column or by a combination of several. `Autoencoder Train` uses the grouping to split the data into training and validation sets, and `Autoencoder Augment Data` to number the copies' cells. `Scale` scales each group on its own. The other analysis tools, among them `Series Analysis` and `Random Forest`, have no `Grouping` setting. Category column headers have a light blue background. All other column headers are gray.

.. image:: /images/data/dataframe.png

The example table has these category columns that you can use for grouping: `Treatment`, `FOV` and `Cell`. When you group by several category columns, you can choose their order (the grouping hierarchy).

.. note::
    The order of the grouping columns changes the order of the rows in the result tables and how the data is arranged in plots. The effect differs from tool to tool. Each tool's page shows it with examples.

.. list-table::
   :widths: 10 10 30
   :header-rows: 1

   * - Icon
     - Analysis Tool
     - Description
   * - .. image:: /images/analysis/calculate.png
     - :doc:`Calculate <calculate>`
     - Adds columns calculated from others, by expressions or functions, for example the FLIM features of the built-in Import workflow.
   * - .. image:: /images/analysis/scale.png
     - :doc:`Scale <scale>`
     - Scales features: standardized, from 0 to 1, or robust to outliers.
   * - .. image:: /images/analysis/summary.png 
     - :doc:`Summarize <summary>`
     - Calculates the count, minimum, maximum, mean, median, standard deviation, standard error of the mean, 25th and 75th percentiles, and sum of grouped data.
   * - .. image:: /images/analysis/relchange.png 
     - :doc:`Relative Change <relchange>`
     - Converts the data to fold-change values, relative to the mean or median of a reference group.
   * - .. image:: /images/analysis/seriesanalysis.png 
     - :doc:`Series Analysis <seriesanalysis>`
     - Analyzes a series of values spread across several table columns.
   * - .. image:: /images/analysis/categorize.png 
     - :doc:`Categorize Data <categorize>`
     - Adds a category column based on value ranges of a feature.
   * - .. image:: /images/analysis/randomforest.png 
     - :doc:`Random Forest <randomforest>`
     - Predicts a category from the features with a random forest, and shows which features matter most.
   * - .. image:: /images/analysis/pca.png 
     - :doc:`PCA <pca>`
     - Principal component analysis: summarizes many features in a few new columns (principal components) and outputs their values.
   * - .. image:: /images/analysis/kmeans.png 
     - :doc:`K-Means <kmeans>`
     - Groups similar data points into clusters.
   * - .. image:: /images/analysis/gmm.png
     - :doc:`Gaussian Mixed Model <gmm>`
     - Groups data points into clusters, each described by a Gaussian (bell-shaped) distribution, and gives each point's probability of belonging to each cluster.
   * - .. image:: /images/analysis/ks.png 
     - :doc:`KS-Statistics <ks>`
     - Compares the distributions of a feature between the groups of a category column, two at a time, with the Kolmogorov–Smirnov test.
   * - .. image:: /images/analysis/aetrain.png 
     - :doc:`Autoencoder Train <aetrain>`
     - Trains an autoencoder model on selected data features. 
   * - .. image:: /images/analysis/aerun.png 
     - :doc:`Autoencoder Run <aerun>`
     - Applies a pre-trained autoencoder model to data.
   * - .. image:: /images/analysis/aeaugment.png 
     - :doc:`Autoencoder Augment Data <aeaugment>`
     - Generates augmented data with a pre-trained autoencoder model.

.. toctree::
    :maxdepth: 2
    :hidden:
    :glob:
    
    calculate
    scale
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


