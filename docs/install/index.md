# Installation

## Requirements

* Python 3.12 or later
* All other Python packages that FLIMAnalyzer needs, including [PyTorch](https://pytorch.org) and [Prefect](https://www.prefect.io), are installed automatically. They are listed in the `pyproject.toml` file of the Git repository [https://github.com/uvaKCCI/flimanalyzer.git](https://github.com/uvaKCCI/flimanalyzer.git).

## Installing with uv (recommended)

[uv](https://docs.astral.sh/uv/) creates a virtual environment (a separate Python setup just for FLIMAnalyzer) in the `.venv` folder of the repository. If needed, it also installs a matching Python version. It then installs FLIMAnalyzer, including the application, with the exact package versions listed in `uv.lock`. FLIMAnalyzer is installed in editable mode, so changes to its code take effect without reinstalling:
```
git clone https://github.com/uvaKCCI/flimanalyzer.git
cd flimanalyzer
uv sync
```
On Windows and Linux (x86_64), uv installs the CUDA 12.8 build of PyTorch, so FLIMAnalyzer can use an NVIDIA GPU. On macOS, uv installs the PyPI build, which can use the Apple GPU (MPS). Only Macs with Apple Silicon are supported, because current PyTorch versions are not available for Intel Macs.

## Installing with pip

```
git clone https://github.com/uvaKCCI/flimanalyzer.git
cd flimanalyzer
python3.12 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[gui]"
```
The `[gui]` part installs the application (wxPython). Without it, `pip install -e .` installs only what [batch mode](/userguide/batch) needs.

pip installs PyTorch from PyPI, which provides a different build on each platform:

* **Linux:** the PyPI build includes CUDA, so an NVIDIA GPU is used if its driver is recent enough.
* **Windows:** the PyPI build is CPU-only. To use an NVIDIA GPU, install the CUDA build before FLIMAnalyzer, for example with `pip install torch --index-url https://download.pytorch.org/whl/cu128`. See [pytorch.org](https://pytorch.org/get-started/locally/) for other CUDA versions.
* **macOS:** only Apple Silicon is supported. The PyPI build uses the Apple GPU (MPS).

Conda users can create the Python environment with conda instead of `venv` and install FLIMAnalyzer into it with pip:
```
conda create -n flimenv python=3.12
conda activate flimenv
pip install -e ".[gui]"
```

## GPU acceleration

The autoencoder tools have a `Device` setting. These tools are `Autoencoder: Train`, `Autoencoder: Run` and `Autoencoder: Augment Data`, and the workflows `FLIM Data Augmentation Tuning` and `FLIM Feature Analysis`. The `Device` setting chooses which processor does the calculations:

* `auto` (default): uses an NVIDIA GPU (`cuda`) if there is one, otherwise the Apple GPU (`mps`), otherwise the CPU.
* `cpu`, `cuda` or `mps`: uses that device, or the CPU if the device is not available.

Trained models are saved so that they don't need a GPU, so a model trained on a GPU can also be used on a computer without one.

## Run the application

**From the command line**

With uv, no activation is needed:
```
uv run flimanalyzer
```
In an activated environment:
```
flimanalyzer
```
To open data files (tab- or comma-separated) at startup, each in its own window:
```
uv run flimanalyzer -i results.txt more-results.csv
```
Run `flimanalyzer --help` for all command-line options.

**Prefect server**

FLIMAnalyzer runs analyses and workflows as [Prefect](https://www.prefect.io) flows. At startup, it connects to a Prefect server: the one set in the active Prefect profile or in the `PREFECT_API_URL` environment variable, or one already running at `http://127.0.0.1:4200/api`. If it finds none, it starts a local server and stops it again when the application closes. See the [README](https://github.com/uvaKCCI/flimanalyzer#prefect-server) for details.

**From Spyder**
1. Launch Spyder.
2. Go to `Tools` > `Preferences` > `Python interpreter`, select `Use the following Python interpreter` and choose the Python program of the FLIMAnalyzer environment, for example `flimanalyzer/.venv/bin/python` (Windows: `flimanalyzer\.venv\Scripts\python.exe`). Spyder needs the `spyder-kernels` package in that environment. Install it with `uv pip install spyder-kernels`.
3. In the Spyder editor, open the `flim/analyzerapp.py` file.
4. Go to `Run` > `Configuration per file...` and check `Execute in external system terminal`.
5. Go to `Run` > `Run`, or click the button with the green triangle in the Spyder toolbar.
