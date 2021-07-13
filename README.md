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

**Windows Installation:**
* Install VS Code

## Installation:

```
git clone https://github.com/uvaKCCI/flimanalyzer.git
cd flimanalyzer
conda env create -f environment.yml
conda activate flimenv
python setup.py install
```

This will create a Conda environment `flimenv` that contains all the Python packages required to run the FLIM Analyzer application.

**MacOS X Installation**

Activate the Conda environment, install the MacOS specific python.app package, and patch the shebang of the flimanalyzer console script.

```
conda activate flimenv
conda install python.app
sed -i '' -e 's/bin\/python/python\.app\/Contents\/MacOS\/python/' $(which flimanalyzer)
```

## Run the application

**From the command line**

On Windows,run this command
```
conda activate flimenv 
flimanalyzer.exe
```

On Mac OSX and Linux, run this command:
```
conda activate flimenv
flimanalyzer
```
