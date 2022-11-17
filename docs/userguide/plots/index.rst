Plots
========

Plotting tools are used to visualize a table's data. Most plotting tools allow the grouping of the table's data by categorical column values. Grouping can be performed by single category or combination of multiple categories. Headers of categorical columns have a light blue background; all other column headers are displayed with a gray background. 

Select a Data Table
-------------------

The shown example table contains the following categorical columns that may be used for data grouping: `Cell, Compartment, FOV, Treatment`.  Grouping by multiple categories follows a customizable hierarchical order. 

.. image:: /images/data/dataframe.png

.. note::
    Changing the order of the grouping hierarchy changes the visualization layout in most plots. The specific effects of different grouping hierarchies on data visualization are  tool dependent and described with examples in the following subsections.

Create a Plot
-------------

.. list-table::
   :widths: 10 10 30
   :header-rows: 1

   * - Icon
     - Analysis Tool
     - Description
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

.. toctree::
    :maxdepth: 2
    :hidden:
    :glob:
    
    barplot
    boxplot
    lineplot
    swarmplot
    violinplot
    scatter
    histogram
    kde
    heatmap

Save a Plot
-----------
While selecting the configuration settings for a given plot, there is an `Autosave` checkbox that saves the produced plot. Simply click on the checkbox and use the `Choose` button to select a directory to save the file to.

