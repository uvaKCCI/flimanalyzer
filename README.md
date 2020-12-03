# FLIMAnalyzer

Python package for analysis of Fluoresence Lifetime Imaging Microscopy (FLIM) data.

## Requirements:

* Python 3.7 (or later)
* pandas
* numpy (1.18)
* matplotlib
* seaborn
* pytorch
* scikit-learn
* xlsxwriter
* wxpython (4.0.7)
* pypubsub
* python.app (for Mac OSX)

## Installation:

```
conda create -n flimenv python=3.7 pandas numpy=1.18 matplotlib seaborn pytorch scikit-learn xlsxwriter python.app -c pytorch
conda activate flimenv
pip install wxpython==4.0.7 pypubsub

git clone https://github.com/uvaKCCI/flimanalyzer.git
```

## Run the application

**From the command line**

On Windows and Linux, run this command
```
conda activate flimenv 
python analyzerapp.py
```

On Mac OSX, run this command:
```
conda activate flimenv
pythonw analyzerapp.py
```

**From Spyder**
1. Launch the Anaconda Navigator
2. In the `Applications on` drop-down, select the name of the conda environment, e.g. `flimenv`. 
3. Launch Spyder.
4. In the Spyder editor, open the `analyzerapp.py` file.
5. Go to `Run`--> `Configuration per file...` and check the box `Execute in external system terminal`.
6. Go to `Run` -->`Run` or click the button with the green triangle in the Spyder toolbar.
