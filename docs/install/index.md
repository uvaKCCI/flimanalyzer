# Installation

## Requirements

* Python 3.12 or later
* All Python dependencies, including [PyTorch](https://pytorch.org), [Prefect](https://www.prefect.io) and [vistiq](https://github.com/ksiller/vistiq), are declared in the `pyproject.toml` file of the code Git repository [https://github.com/uvaKCCI/flimanalyzer.git](https://github.com/uvaKCCI/flimanalyzer.git) and installed automatically.

## Installing with uv (recommended)

[uv](https://docs.astral.sh/uv/) creates a virtual environment in the `.venv` folder of the repository, installs a matching Python version if needed, and installs FLIMAnalyzer in editable mode with the exact package versions recorded in `uv.lock`:
```
git clone https://github.com/uvaKCCI/flimanalyzer.git
cd flimanalyzer
uv sync
```
On Windows and Linux (x86_64), uv installs the CUDA build of PyTorch; on macOS the standard PyPI build is used.

## Installing with pip

```
git clone https://github.com/uvaKCCI/flimanalyzer.git
cd flimanalyzer
python3.12 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .
```
pip installs the CPU build of PyTorch from PyPI. For GPU support, install PyTorch first by following the instructions at [pytorch.org](https://pytorch.org/get-started/locally/).

Conda users can create the Python environment with conda instead of `venv` and install FLIMAnalyzer into it with pip:
```
conda create -n flimenv python=3.12
conda activate flimenv
pip install -e .
```

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
Run `flimanalyzer --help` for all command line options.

**Prefect server**

FLIMAnalyzer runs analyses and workflows as [Prefect](https://www.prefect.io) flows. At startup it uses the Prefect server configured in the active Prefect profile or in the `PREFECT_API_URL` environment variable, or a server already running at `http://127.0.0.1:4200/api`. If none is found, it starts a local server and stops it again when the application exits. See the [README](https://github.com/uvaKCCI/flimanalyzer#prefect-server) for details.

**From Spyder**
1. Launch Spyder.
2. Go to `Tools` --> `Preferences` --> `Python interpreter`, select `Use the following Python interpreter` and choose the Python executable of the FLIMAnalyzer environment, e.g. `flimanalyzer/.venv/bin/python` (Windows: `flimanalyzer\.venv\Scripts\python.exe`). Spyder requires the `spyder-kernels` package in that environment (`uv pip install spyder-kernels`).
3. In the Spyder editor, open the `flim/analyzerapp.py` file.
4. Go to `Run` --> `Configuration per file...` and check the box `Execute in external system terminal`.
5. Go to `Run` --> `Run` or click the button with the green triangle in the Spyder toolbar.
