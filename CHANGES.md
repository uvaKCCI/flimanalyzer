# Changes

## 0.6.1

### Results that change

- **Relative Change** aligns the reference values on the grouping columns only,
  not on every other category column. Rows outside the reference group were NaN
  when a non-grouping category (e.g. Cell) had values that the reference rows
  lacked; such rows now keep their relative values (#178).

## 0.6.0

The first release on current Python and package versions (Python 3.12, Prefect 3,
pandas 2, wxPython 4.2, PyTorch 2). FLIMAnalyzer is now installed with uv or pip (see
the README), instead of with the 0.5 series' `environment.yml`. The core (tools, workflows,
settings) is separate from the graphical user interface (GUI), so FLIMAnalyzer also runs
without it, in batch mode. Settings files of all earlier versions load.

### Results that change

- **Basic FLIRR Analysis** divides by the mean or median of a chosen reference category
  (new setting "Reference value", default "Ctrl"). 0.5.x used the value in the first
  row as the reference, so results differ when the first row is not in the reference
  category (#157).
- **Scatter, Box, Violin and Swarm plots** fit their value axes to the data (new
  setting "Fit axes to the data", on by default). In 0.5.x the axes always included 0,
  which squeezed data far from 0 (#158). Turn the setting off for the old axes.

### New

- **Batch mode:** `flimbatch` (or `flimanalyzer --batch`) imports data and runs tools
  and workflows without the GUI, e.g. on a computing cluster.
- **Installation without the GUI:** wxPython is optional (the `gui` extra), for
  computers without a display, such as cluster nodes.
- **Docker images** of batch mode on ghcr.io: `ghcr.io/uvakcci/flimanalyzer`, with
  the CUDA build of PyTorch or CPU only (`-cpu`).
- **PyPI:** FLIMAnalyzer is published on PyPI as `flimanalyzer`.
- **Concurrent and distributed execution:** steps that don't depend on each other run
  at the same time, as threads by default. Optional Dask executors run them in
  separate processes on one computer, or on a Dask cluster. Every task is tagged with
  its tool's name, so a Prefect concurrency limit on a tool (e.g. `Autoencoder: Train`)
  applies everywhere, also inside workflows.
- **Progress dialog:** shows the tasks, a link to Prefect and the folder the results are
  saved in, and has a Cancel button. Long folder paths are shortened, with the full
  path in the tooltip.
- **Run summary:** each step's status, resources and notes.
- **Tool dialogs** are redesigned: generated from the tools' settings, checked while
  typing, with markers for problems. Each dialog has Load Settings and Save Settings.
- **Settings files** have a section per tool. The File menu has Import Settings and
  Export Settings.
- **Workflows** check their settings against the data before they run, and suggest
  close column names when a column is missing.
- **Data tools:** new Split; Concatenate by rows or by columns; Unpivot by header
  level.
- **Plots** follow the category order on the axes and in the legends; legend position;
  several plots in one figure.
- **Autoencoder tools** use the GPU automatically (NVIDIA CUDA or Apple MPS) and fall
  back to the CPU.
- **Help menu** with links to the documentation and an About dialog. New icons in one
  colour-blind safe style.
- **Documentation:** user guide pages for batch mode, Docker, settings, the Filter
  tool, and concurrent and distributed execution (including `flimbatch` on HPC
  clusters with Slurm; those examples are not tested on a cluster). All screenshots
  are from 0.6.0. API reference.

### Fixes

- **Autosave to a mapped network drive** (Windows): the results were not saved in the
  chosen folder (#163). The folder is now stored as its full network path
  (`\\server\share\...`), and the dialogs and batch mode report a folder that can't be
  reached or written to before the run, instead of silently saving elsewhere. Not
  verified on Windows yet; please report in #163 whether it works for you.
- **Tall dialogs** (e.g. Tuning) no longer run off the screen: they scroll and fit the
  usable screen area, OK button included, also on small screens (#42).
- **AE Training** with the CPU selected warned about CUDA; the CPU path no longer
  queries CUDA (#143).
- **Filter Settings dialog:** the "Dropped view" column could show counts like `123:,`
  (#164).
- **Configuration dialogs** failed with wxPython 4.1 and later, so 0.5.x needs its
  pinned environment (#159). 0.6.0 runs on current wxPython (4.2).

### Removed

- The old plugin interface (#153). Tools are written against the new core interface;
  see the API reference.

## 0.5.2

Bug fixes for 0.5.1; no results change. Same requirements as 0.5.0 (`environment.yml`).

### Fixes

- **Import:** the Import dialog failed to open once the settings named a filename
  parser, e.g. after an import with one (#149).
- **Filter Settings dialog:** the title read "Filter Settings TEST" and the counts of
  dropped and remaining rows always showed "???" (#150).
- **Category filter** (right-click on a category column header): the values are listed
  in the category order set with Order Categories, not in the order they occur in the
  data (#151).
- **AE Training:** the default model "Autoencoder 2" does not exist; the default is now
  "AE Dimensionality Reduction 2-10". The dialog used to fall back to the first model;
  scripted use failed (#152).

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
