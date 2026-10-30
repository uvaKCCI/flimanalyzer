# Changes

## 0.5.1

Bug fixes for 0.5.0. Same requirements as 0.5.0: install with `environment.yml`
(Python 3.7, Prefect 1.3, pandas 1.1, wxPython 4.0.4, PyTorch 1.7). Newer wxPython
versions (4.1 and later) are not supported by the 0.5 series; FLIMAnalyzer 0.6 runs on
current Python and package versions.

### Results that change

- **FLIM Feature Analysis** used to skip every time point whose name contains "15"
  (e.g. "15 min", "T15"). All time points are now used, in the order of their
  categories (see Order Categories). Results of data sets with such time points differ
  from 0.5.0.
- **Line, Box, Swarm and Violin plots** follow the category order set with Order
  Categories, on the axes and in the legends. Line plots used to sort the x axis
  alphabetically.
- **AE Training** model files are named without a stray dot (`..._1e-08_epoch0001.model`,
  was `..._1e-0.8_epoch0001.model`). Existing model files keep their names and still
  load.
- **AE Training** saves the models on the CPU, so models trained on a GPU (cuda) load
  and run on any computer.

### Fixes

- **PCA:** when a selected feature has missing values, the principal components were
  put on the wrong rows (and categories); with one feature, a row number column was
  included in the PCA.
- **Frequency Histogram:** with two or more grouping columns, the legend labels were in
  a different order than the histograms, so series were mislabeled.
- **Frequency Histogram dialog:** the settings of FLIRR, NAD(P)H tm and other features
  with built-in defaults could not be opened; negative ranges can be entered; a
  feature without its own settings gets 100 bins (not the bins of the previous
  feature).
- **KDE:** "single plot" with one feature failed.
- **KS-Statistics:** failed when the only grouping column is the comparison column.
- **Random Forest:** failed when a grouping column is also a selected feature.
- **AE Augment:** the augmented table had an extra "index" feature column.
- **Bar plot:** a feature without values gives an empty plot instead of an error.
- **Import:** if no file can be read, a message is shown instead of an error; importing
  several files names the window "Imported Data" (not after the first file).
- **Saving a table** no longer changes the column names of the table shown, and works
  with columns whose names are not text.
- **Order Categories:** category settings no longer carry over from one data set to
  another.
- **Opening a file** no longer marks it as modified, so closing its window doesn't ask
  to save it.
- **Startup:** FLIMAnalyzer installed with `python setup.py install` failed to start
  unless run from inside the source folder (it looked for the version in a git
  checkout).

### Documentation

- The documentation builds on Read the Docs again (current build images; the 0.5.0
  configuration is no longer supported there).
