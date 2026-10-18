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
On Windows and Linux (x86_64), uv installs the CUDA 12.8 build of PyTorch, so an NVIDIA GPU can be used. On macOS (Apple Silicon only, as current PyTorch has no Intel Mac builds), the PyPI build is used, which supports the Apple GPU (MPS).

## Installing with pip

```
git clone https://github.com/uvaKCCI/flimanalyzer.git
cd flimanalyzer
python3.12 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .
```
pip installs PyTorch from PyPI, which provides a different build on each platform:

* **Linux:** the PyPI build includes CUDA, so an NVIDIA GPU is used if its driver is recent enough.
* **Windows:** the PyPI build is CPU-only. For an NVIDIA GPU, install the CUDA build before FLIMAnalyzer, for example `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`; see [pytorch.org](https://pytorch.org/get-started/locally/) for other CUDA versions.
* **macOS:** only Apple Silicon is supported; the PyPI build uses the Apple GPU (MPS).

Conda users can create the Python environment with conda instead of `venv` and install FLIMAnalyzer into it with pip:
```
conda create -n flimenv python=3.12
conda activate flimenv
pip install -e .
```

## GPU acceleration

The autoencoder tools (Autoencoder: Train, Run and Augment Data, and the FLIM Data Augmentation Tuning and FLIM Feature Analysis workflows) have a **Device** setting:

* `auto` (default): an NVIDIA GPU (`cuda`) if available, otherwise the Apple GPU (`mps`), otherwise the CPU.
* `cpu`, `cuda` or `mps`: uses the specified device and falls back to CPU if not available.

Trained models are saved on the CPU, so a model trained on one machine can be used on any other.

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
To open data files (tab- or comma-separated) right away, each in its own window:
```
uv run flimanalyzer -i results.txt more-results.csv
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
