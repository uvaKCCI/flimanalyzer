# Introduction

## Concept

FLIMAnalyzer is free software for analyzing fluorescence lifetime imaging microscopy (FLIM) data. It is written in Python by the UVA Keck Center for Cellular Imaging. Its code is in the public GitHub repository [uvaKCCI/flimanalyzer](https://github.com/uvaKCCI/flimanalyzer).

FLIMAnalyzer reads fitted FLIM data from text files laid out like a spreadsheet, usually tab-separated `.txt` files or comma-separated `.csv` files. It combines several files into one table, and it can read values such as the treatment or the cell from the file names (see [Loading Data](/userguide/data/load)). The tables can then be filtered, sorted, rearranged and summarized (see [Data Tables](/userguide/data/index)).

The analysis tools include summaries, relative changes, Kolmogorov-Smirnov (KS) statistics, principal component analysis (PCA), clustering and random forests (see [Analysis](/userguide/analysis/index)). Many of them use the scikit-learn package. The plots use the pandas, matplotlib and seaborn packages (see [Plots](/userguide/plots/index)). Autoencoders, built with PyTorch, reduce the features to a few values or make augmented (simulated) data; tools for tuning their training are included.

There are three ways to work with FLIMAnalyzer:

* **The GUI** (graphical user interface): open data, choose a tool from a menu or the tool panel, set its options in a dialog, and see the results in table and plot windows (see [Menus](/userguide/appmenu) and [Tool dialogs](/userguide/dialogs)).
* **Workflows** run several tools in one go, for example summaries, relative changes and plots of the same features (see [Workflows](/userguide/workflows)).
* **Batch mode** (`flimbatch`) runs tools and workflows without the GUI, with the settings saved in the GUI, for example on a computing cluster (see [Batch Mode](/userguide/batch)).
