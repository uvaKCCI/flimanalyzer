Plots
========

The plotting tools show the data of a table as plots. Most plotting tools can group the data by the values in category columns. The `Pair Plot` uses only the first grouping column, the `FLIRR Plot` needs at least one, and in the `Heatmap` the grouping has no effect. You can group by a single category column or by several. In the table, the headers of category columns have a light blue background. All other column headers have a gray background.

Select a Data Table
-------------------

The example table has these category columns, which you can use to group the data: `Cell`, `Compartment`, `FOV` and `Treatment`. When you group by several columns, the order of the columns matters: the data is grouped by the first column, then by the second, and so on. You can change this order.

.. image:: /images/data/dataframe.png

.. note::
    In most plots, changing the order of the grouping columns changes the plot layout. The effect depends on the tool. The page of each tool shows examples.

Create a Plot
-------------

.. list-table::
   :widths: 10 10 30
   :header-rows: 1

   * - Icon
     - Plot Tool
     - Description
   * - .. image:: /images/analysis/barplot.png 
     - `Bar Plot <barplot.html>`_
     - Creates bar plots of the mean +/- standard deviation (or S.E.M.) of grouped data.
   * - .. image:: /images/analysis/boxplot.png 
     - `Box Plot <boxplot.html>`_
     - Creates box plots of grouped data.
   * - .. image:: /images/analysis/lineplot.png 
     - `Line Plot <lineplot.html>`_
     - Creates line plots of grouped data.
   * - .. image:: /images/analysis/swarmplot.png 
     - `Swarm Plot <swarmplot.html>`_
     - Creates swarm plots of grouped data.
   * - .. image:: /images/analysis/violinplot.png 
     - `Violin Plot <violinplot.html>`_
     - Creates violin plots of grouped data.
   * - .. image:: /images/analysis/scatter.png 
     - `Scatter Plot <scatter.html>`_
     - Creates scatter plots of pairs of selected features in grouped data.
   * - .. image:: /images/analysis/pairplot.png
     - `Pair Plot <pairplot.html>`_
     - Creates a grid of scatter plots of feature pairs in grouped data.
   * - .. image:: /images/analysis/histogram.png 
     - `Frequency Histogram <histogram.html>`_
     - Creates frequency histograms of grouped data.
   * - .. image:: /images/analysis/kde.png 
     - `KDE Plot <kde.html>`_
     - Creates kernel density estimate (KDE) plots of grouped data.
   * - .. image:: /images/analysis/heatmap.png 
     - `Heatmap <heatmap.html>`_
     - Creates a heatmap of the correlations between features, using all rows.
   * - .. image:: /images/analysis/flirrplot.png 
     - `FLIRR Plot <flirr.html>`_
     - Creates a figure with several plots of FLIRR.

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
    pairplot
    histogram
    kde
    heatmap
    flirr
    plotwindow

Plot Windows and Saving
-----------------------

Each plot opens in a plot window. There you can zoom into the plot, change its axes, labels and line colors, and save it as an image file. See :doc:`plotwindow`.

The options common to all tool dialogs, such as the choice of the data and the result prefix, are described in :doc:`/userguide/dialogs`. To save the plots automatically each time a tool runs, check `Save results in` in the tool's dialog (see `Saving results <../dialogs.html#saving-results>`_). Plots are saved as PNG files.
