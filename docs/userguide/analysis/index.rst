Analysis
========

.. toctree::
    :maxdepth: 2
    :hidden:
    :glob:
    
    *

Most analysis tools allow the grouping of data by categorical column values to summarize the underlying data. Grouping can be performed by single category or combination of multiple categories. Grouping by multiple categories follows a customizable hierarchical order. 

.. note::
    Changing the order of the grouping hierarchy changes ordering of rows of resulting data tables and data presentation in plots. The specific effects of different grouping hierarchies on data representation are analysis tool dependent and described with examples in the following subsections.

.. list-table::
   :widths: 10 10 30
   :header-rows: 1

   * - Icon
     - Analysis Tool
     - Description
   * - .. image:: /images/analysis/summary.png 
     - `Summary Table </userguide/analysis/summarystats.html>`_
     - Calculates counts, min, max, mean, median, StDev, S.E.M, <br>25t percentile, and 75 percentile of grouped data.
   * - .. image:: /images/analysis/relchange.png 
     - `Relative Change </userguide/analysis/relchange.html>`_
     - Converts input data to fold-change values relative to mean/median of reference group.
   * - .. image:: /images/analysis/barplot.png 
     - `Barplot </userguide/analysis/barplot.html>`_
     - Creates bar plot based on mean +/- StDev (or S.E.M)<br> of grouped data.
   * - .. image:: /images/analysis/boxplot.png 
     - `Boxplot </userguide/analysis/boxplot.html>`_
     - Creates box plot of grouped data. 
   * - .. image:: /images/analysis/lineplot.png 
     - `Lineplot </userguide/analysis/lineplot.html>`_
     - Creates line plot of grouped data. 
   * - .. image:: /images/analysis/scatter.png 
     - `Scatter Plot </userguide/analysis/scatter.html>`_
     - Creates scatter plot for pairs of selected features in grouped<br> data. 
   * - .. image:: /images/analysis/histogram.png 
     - `Frequency Histogram </userguide/analysis/histogram.html>`_
     - Creates frequency histogram of grouped data. 
   * - .. image:: /images/analysis/kde.png 
     - `KDE Plot </userguide/analysis/kde.html>`_
     - Creates kernel density estimate (kde) plot of grouped data.
   * - .. image:: /images/analysis/heatmap.png 
     - `Heatmap </userguide/analysis/heatmap.html>`_
     - Creates heatmap for matrix of data features based on <br>mean of grouped data. 
   * - .. image:: /images/analysis/randomforest.png 
     - `Random Forest </userguide/analysis/randomforest.html>`_
     - Performs a random forest classification analysis for grouped<br> data. 
   * - .. image:: /images/analysis/pca.png 
     - `Principal Component Analysis </userguide/analysis/pca.html>`_
     - Performs a principal component analysis for grouped<br> data. 
   * - .. image:: /images/analysis/aetrain.png 
     - `Autoencoder Training </userguide/analysis/aetrain.html>`_
     - Trains an autoencoder model on selected data features. 
   * - .. image:: /images/analysis/aerun.png 
     - `Autoencoder Analysis </userguide/analysis/aerun.html>`_
     - Applies a pre-trained autoencoder model to data.



