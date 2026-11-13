# Introduction

## Concept

FLIMAnalyzer is open source software for the analysis of fluorescence lifetime imaging microscopy (FLIM) data. The code is in the public GitHub repository [uvaKCCI/flimanalyzer](https://github.com/uvaKCCI/flimanalyzer).

FLIMAnalyzer reads FLIM data from text files. Each file contains a table of fitted values. Usually, tabs (`.txt` files) or commas (`.csv` files) separate the columns. The built-in `Import` workflow combines the tables of many files into one table. It also gets values from the file names, for example the treatment or the cell (see [Loading Data](/userguide/data/load)). You can filter, sort, change and summarize the tables (see [Data Tables](/userguide/data/index)).

The analysis tools calculate summaries, relative changes and Kolmogorov-Smirnov (KS) statistics. They also do principal component analysis (PCA), clustering and random forest classification (see [Analysis](/userguide/analysis/index)). Many of these tools use the scikit-learn package. The plot tools use the pandas, matplotlib and seaborn packages (see [Plots](/userguide/plots/index)).

The autoencoder tools use the PyTorch package. An autoencoder decreases the number of features to a small number of values. It can also make augmented (simulated) data. Other tools help you to find good settings for the training of an autoencoder.

You can use FLIMAnalyzer in two modes:

* **GUI** (graphical user interface): Open the data. Select a tool in a menu or in the tool panel. Set the tool settings in the dialog of the tool. The results show in table windows and plot windows (see [Menus](/userguide/appmenu) and [Tool dialogs](/userguide/dialogs)).
* **Batch mode** (`flimbatch`): FLIMAnalyzer runs the tools without the GUI, for example on a computing cluster. The tool settings come from an app settings file. You can export this file from the GUI (see [Batch Mode](/userguide/batch)).

In the GUI and in batch mode, a workflow runs a sequence of tools. For example, a workflow can make summaries, relative changes and plots of the same features (see [Workflows](/userguide/workflows)).
