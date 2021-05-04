# Installation

## Requirements

**Python Packages:**
* Python 3.7 (or later)
* pandas
* numpy (1.18)
* matplotlib
* seaborn
* pytorch
* scikit-learn
* xlsxwriter
* wxpython
* networkx
* pypubsub
* python.app (for MacOS X)

## Creating a Conda environment

The code Git repository [https://github.com/uvaKCCI/flimanalyzer.git](https://github.com/uvaKCCI/flimanalyzer.git) contains an `environment.yml` file defining required Python packages. The `python.app` package, only required for MacOS X, is not included in the environment file and has to be installed manually, see below.

Run the following commands to create a `flimenv` Conda environment based on the `environemnt.yml` file:
```
git clone https://github.com/uvaKCCI/flimanalyzer.git
cd flimanalyzer
conda env create -f environment.yml
python setup.py install
```
Installations on Windows and MacOS require a couple additional steps.

**Windows Installation**

Install VS Code.

**MacOS X Installation**

Activate the Conda environment, install the MacOS specific `python.app` package, and patch the shebang of the `flimanalyzer` console script. 
```
conda activate flimenv
conda install python.app
sed -i '' -e 's/bin\/python/python\.app\/Contents\/MacOS\/python/' $(which flimanalyzer)
```

## Run the application

**From the command line**

On Windows and Linux, run this command
```
conda activate flimenv 
flimanalyzer
```


**From Anaconda Spyder**
1. Launch the Anaconda Navigator
2. In the `Applications on` drop-down, select the name of the conda environment, e.g. `flimenv`. 
3. Launch Spyder.
4. In the Spyder editor, open the `analyzerapp.py` file.
5. Go to `Run`--> `Configuration per file...` and check the box `Execute in external system terminal`.
6. Go to `Run` -->`Run` or click the button with the green triangle in the Spyder toolbar.
