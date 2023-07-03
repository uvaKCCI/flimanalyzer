Analysis
========

Most analysis tools allow the grouping of data by categorical column values to summarize the underlying data. Grouping can be performed by single category or combination of multiple categories. Headers of categorical columns have a light blue background; all other column headers are displayed with a gray background.

.. image:: /images/data/dataframe.png

The shown example table contains the following categorical columns that may be used for data grouping: `Cell, Compartment, FOV, Treatment`.  Grouping by multiple categories follows a customizable hierarchical order. 

.. note::
    Changing the order of the grouping hierarchy changes ordering of rows of resulting data tables and data presentation in plots. The specific effects of different grouping hierarchies on data representation are analysis tool dependent and described with examples in the following subsections.

.. list-table::
   :widths: 10 10 30
   :header-rows: 1

   * - Icon
     - Analysis Tool
     - Description
   * - .. image:: /images/analysis/summary.png 
     - `Summary Table <summary.html>`_
     - Calculates counts, min, max, mean, median, StDev, S.E.M,    
25th percentile, and 75th percentile of grouped data.
   * - .. image:: /images/analysis/relchange.png 
     - `Relative Change <relchange.html>`_
     - Converts input data to fold-change values relative to mean/median of reference group.
   * - .. image:: /images/analysis/seriesanalysis.png 
     - `Series Analysis <seriesanalysis.html>`_
     - Performs an analysis of a data series spread across multiple table columns. 
   * - .. image:: /images/analysis/categorize.png 
     - `Categorize Data <categorize.html>`_
     - categorizes data based on thresholded value bins in a specified table column. 
   * - .. image:: /images/analysis/randomforest.png 
     - `Random Forest <randomforest.html>`_
     - Performs a random forest classification analysis for grouped data. 
   * - .. image:: /images/analysis/pca.png 
     - `Principal Component Analysis <pca.html>`_
     - Reduces the dimensionality of dataset and outputs principal component values. 
   * - .. image:: /images/analysis/kmeans.png 
     - `K-Means <kmeans.html>`_
     - Groups similar data points into clusters.
   * - .. image:: /images/analysis/ks.png 
     - `KS Statistics <ks.html>`_
     - Applies Kolmogorov–Smirnov test, to measure similarity between sample and theoretical distributions.
   * - .. image:: /images/analysis/aetrain.png 
     - `Autoencoder Training <aetrain.html>`_
     - Trains an autoencoder model on selected data features. 
   * - .. image:: /images/analysis/aerun.png 
     - `Autoencoder Analysis <aerun.html>`_
     - Applies a pre-trained autoencoder model to data.
   * - .. image:: /images/analysis/aerun.png 
     - `Autoencoder Simulate <aesim.html>`_
     - Simulate..

.. toctree::
    :maxdepth: 2
    :hidden:
    :glob:
    
    summary
    relchange
    seriesanalysis
    categorize
    merge
    heatmap
    randomforest
    pca
    kmeans
    ks
    aetrain
    aerun
    aesim


