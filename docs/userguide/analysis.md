# Analysis

The FLIMAnalyzer software provides several built-in tools to analyze data. The tools are available in the `Analysis` menu or the application toolbar.

| Tool Icon | Analysis Tool | Description |
|:---------:|:-------------:|:-----------:|
| ![](/images/analysis/summary.png) | [Summary Statistics](/userguide/analysis/summarystats) | Calculates counts, min, max, mean, median, StDev, S.E.M, <br>25t percentile, and 75 percentile of grouped data. |
| ![](/images/analysis/relchange.png) | [Relative Change](#relative-change) | Converts input data to fold-change values relative to<br> mean/median of reference group. |
| ![](/images/analysis/meanbar.png) | [Mean Barplot](#mean-barplot) | Creates bar plot based on mean +/- StDev (or S.E.M)<br> of grouped data. |
| ![](/images/analysis/boxplot.png) | [Boxplot](#boxplot) | Creates box plot of grouped data. |
| ![](/images/analysis/lineplot.png) | [Lineplot](#lineplot) | Creates line plot of grouped data. |
| ![](/images/analysis/heatmap.png) | [Heatmap](#heatmap) | Creates heatmap for matrix of data features based on <br>mean of grouped data. |
| ![](/images/analysis/histogram.png) | [Frequency Histogram](#frequency-histogram) | Creates frequency histogram of grouped data. |
| ![](/images/analysis/kde.png) | [KDE Plot](#kde-plot) | Creates kernel density estimate (kde) plot of grouped data. |
| ![](/images/analysis/scatter.png) | [Scatter Plot](#scatter-plot) | Creates scatter plot for pairs of selected features in grouped<br> data. |
| ![](/images/analysis/randomforest.png) | [Random Forest Analysis](#random-forest-analysis) | Performs a random forest classification analysis for grouped<br> data. |
| ![](/images/analysis/pca.png) | [Principal Component Analysis](#principal-component-analysis) | Performs a principal component analysis for grouped<br> data. |
| ![](/images/analysis/aetrain.png) | [Autoencoder Training](#autoencoder-training) | Trains an autoencoder model on selected data features. |
| ![](/images/analysis/aerun.png) | [Autoencoder Analysis](#autoencoder-analysis) | Applies a pre-trained autoencoder model to data. |

## Summary Statistics

Most analysis tools allow the grouping of data by categorical column values to summarize the underlying data. Grouping can be performed by single category or combination of multiple categories. Grouping by multiple categories follows a customizable hierarchical order. Changing the order of the grouping hierarchy changes ordering of rows of resulting data tables and data presentation in plots. The specific effects of different grouping hierarchies on data representation are analysis tool dependent and described with examples in the following subsections.

![](/images/data/dataframe.png)

![](/images/analysis/summary-nogrouping.png)

![](/images/analysis/summary-result1-nogrouping.png)

![](/images/analysis/summary-result2-nogrouping.png)

## Relative Change

## Mean Barplot

## Boxplot

## Lineplot

## Heatmap

## Frequency Histogram

## KDE Plot

## Scatter Plot

## Random Forest Analysis

## Principal Component Analysis

## Autoencoder Training

## Autoencoder Analysis
