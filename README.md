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
* python.app (for Mac OSX)

## Installation:

```
conda create -n flimenv python=3.7 pandas numpy=1.18 matplotlib seaborn pytorch scikit-learn xlsxwriter -c pytorch
conda activate flimenv
pip install wxpython==4.0.7

git clone https://github.com/uvaKCCI/flimanalyzer.git
```

## Run the application

**From the command line**
On Windows and Linux, run this command
```
python analyzerapp.py
```

On Mac OSX, run this command:
```
pythonw analyzerapp.py
```

**From Spyder**
1. In the Spyder editor, open the `analyzerapp.py` file.
2. Go to `Run`--> `Configuration per file...` and check the box `Execute in external system terminal`.
