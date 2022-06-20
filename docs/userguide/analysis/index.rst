Analysis
========

Most analysis tools allow the grouping of data by categorical column values to summarize the underlying data. Grouping can be performed by single category or combination of multiple categories. Headers of categorical columns have a light blue background; all other column headers are displayed with a gray background.

.. image:: /images/data/dataframe.png

The shown example table contains the following categorical columsn that may be used for data grouping: `Cell, Compartment, FOV, Treatment`.  Grouping by multiple categories follows a customizable hierarchical order. 

.. note::
    Changing the order of the grouping hierarchy changes ordering of rows of resulting data tables and data presentation in plots. The specific effects of different grouping hierarchies on data representation are analysis tool dependent and described with examples in the following subsections.

.. list-table::
   :widths: 10 10 30
   :header-rows: 1

   * - Icon
     - Analysis Tool
     - Description
   * - .. image:: /images/analysis/summary.png 
     - `Summary Table <summarystats.html>`_
     - Calculates counts, min, max, mean, median, StDev, S.E.M, <br>25t percentile, and 75 percentile of grouped data.
   * - .. image:: /images/analysis/relchange.png 
     - `Relative Change <relchange.html>`_
     - Converts input data to fold-change values relative to mean/median of reference group.
   * - .. image:: /images/analysis/seriesanalysis.png 
     - `Series Analysis <seriesanalysis.html>`_
     - Performs an analysis of a data series spread across multiple table columns. 
   * - .. image:: /images/analysis/categorize.png 
     - `Categorize Data <categorize.html>`_
     - categorizes data based on thresholded value bins in a specified table column. 
   * - .. image:: /images/analysis/merge.png 
     - `Merge Data <merge.html>`_
     - Merges two data tables based on shared category columns. 
   * - .. image:: /images/analysis/barplot.png 
     - `Barplot <barplot.html>`_
     - Creates bar plot based on mean +/- StDev (or S.E.M)<br> of grouped data.
   * - .. image:: /images/analysis/boxplot.png 
     - `Boxplot <boxplot.html>`_
     - Creates box plot of grouped data. 
   * - .. image:: /images/analysis/lineplot.png 
     - `Lineplot <lineplot.html>`_
     - Creates line plot of grouped data. 
   * - .. image:: /images/analysis/swarmplot.png 
     - `Swarmplot <swarmplot.html>`_
     - Creates swarm plot of grouped data. 
   * - .. image:: /images/analysis/violinplot.png 
     - `Violinplot <violinplot.html>`_
     - Creates violin plot of grouped data. 
   * - .. image:: /images/analysis/scatter.png 
     - `Scatter Plot <scatter.html>`_
     - Creates scatter plot for pairs of selected features in grouped data. 
   * - .. image:: /images/analysis/histogram.png 
     - `Frequency Histogram <histogram.html>`_
     - Creates frequency histogram of grouped data. 
   * - .. image:: /images/analysis/kde.png 
     - `KDE Plot <kde.html>`_
     - Creates kernel density estimate (kde) plot of grouped data.
   * - .. image:: /images/analysis/heatmap.png 
     - `Heatmap <heatmap.html>`_
     - Creates heatmap for matrix of data features based on mean of grouped data. 
   * - .. image:: /images/analysis/randomforest.png 
     - `Random Forest <randomforest.html>`_
     - Performs a random forest classification analysis for grouped data. 
   * - .. image:: /images/analysis/pca.png 
     - `Principal Component Analysis <pca.html>`_
     - Performs a principal component analysis for grouped data. 
   * - .. image:: /images/analysis/aetrain.png 
     - `Autoencoder Training <aetrain.html>`_
     - Trains an autoencoder model on selected data features. 
   * - .. image:: /images/analysis/aerun.png 
     - `Autoencoder Analysis <aerun.html>`_
     - Applies a pre-trained autoencoder model to data.

.. toctree::
    :maxdepth: 2
    :hidden:
    :glob:
    
    summary
    relchange
    seriesanalysis
    categorize
    merge
    barplot
    boxplot
    lineplot
    swarmplot
    violinplot
    scatter
    histogram
    kde
    heatmap
    randomforest
    pca
    aetrain
    aerun


