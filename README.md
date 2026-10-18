# <img src="flim/resources/flimanalyzer.png" alt="" width="80" align="top"> FLIMAnalyzer

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://github.com/uvaKCCI/flimanalyzer/blob/main/pyproject.toml) [![Tests](https://github.com/uvaKCCI/flimanalyzer/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/uvaKCCI/flimanalyzer/actions/workflows/tests.yml) [![codecov](https://codecov.io/gh/uvaKCCI/flimanalyzer/branch/main/graph/badge.svg)](https://codecov.io/gh/uvaKCCI/flimanalyzer) [![Documentation Status](https://readthedocs.org/projects/flimanalyzer/badge/?version=latest)](https://flimanalyzer.readthedocs.io/en/latest/) [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23426563.svg)](https://doi.org/10.5281/zenodo.23426563)

Python package for analysis of Fluorescence Lifetime Imaging Microscopy (FLIM) data.

Documentation: https://flimanalyzer.readthedocs.io

## Requirements

* Python 3.12 or later
* All Python dependencies, including [PyTorch](https://pytorch.org), [Prefect](https://www.prefect.io) and [vistiq](https://github.com/ksiller/vistiq), are declared in `pyproject.toml` and installed automatically.

## Installation

### With uv (recommended)

Clone the repository and let [uv](https://docs.astral.sh/uv/) create the environment. `uv sync` creates `.venv`, installs a matching Python if needed, and installs FLIMAnalyzer in editable mode with the exact package versions from `uv.lock`:

    git clone https://github.com/uvaKCCI/flimanalyzer.git
    cd flimanalyzer
    uv sync

On Windows and Linux (x86_64), uv installs the CUDA 12.8 build of PyTorch, so an NVIDIA GPU can be used. On macOS (Apple Silicon only, as current PyTorch has no Intel Mac builds), the PyPI build is used, which supports the Apple GPU (MPS).

To also install the test dependencies:

    uv sync --extra test

### With pip

    git clone https://github.com/uvaKCCI/flimanalyzer.git
    cd flimanalyzer
    python3.12 -m venv .venv
    source .venv/bin/activate    # Windows: .venv\Scripts\activate
    pip install -e .

pip installs PyTorch from PyPI, which provides a different build on each platform:

* **Linux:** the PyPI build includes CUDA, so an NVIDIA GPU is used if its driver is recent enough.
* **Windows:** the PyPI build is CPU-only. For an NVIDIA GPU, install the CUDA build before FLIMAnalyzer, for example `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`; see [pytorch.org](https://pytorch.org/get-started/locally/) for other CUDA versions.
* **macOS:** only Apple Silicon is supported; the PyPI build uses the Apple GPU (MPS).

## GPU acceleration

The autoencoder tools (Autoencoder: Train, Run and Augment Data, and the FLIM Data Augmentation Tuning and FLIM Feature Analysis workflows) have a **Device** setting:

* `auto` (default): an NVIDIA GPU (`cuda`) if available, otherwise the Apple GPU (`mps`), otherwise the CPU.
* `cpu`, `cuda` or `mps`: that device. If it is not available, the CPU is used and a warning is logged.

Trained models are saved on the CPU, so a model trained on one machine can be used on any other.

## Run the application

With uv, no activation is needed:

    uv run flimanalyzer

In an activated environment:

    flimanalyzer

Run `flimanalyzer --help` for all command line options.

## Prefect server

FLIMAnalyzer runs analyses and workflows as [Prefect](https://www.prefect.io) flows. At startup it looks for a Prefect server in this order:

1. The server configured in the active Prefect profile or in the `PREFECT_API_URL` environment variable, e.g.

       prefect profile use <profile>
       # or
       export PREFECT_API_URL=https://my-prefect-server/api

2. A server already running locally at `http://127.0.0.1:4200/api`.
3. If none is found, FLIMAnalyzer starts a local server (`prefect server start`) and stops it again when the application exits. The server's output is written to `prefect-server.log`.

Flow and task runs can be inspected in the Prefect UI of the server in use, e.g. [http://127.0.0.1:4200](http://127.0.0.1:4200) for a local server. To keep a local server running across sessions, start it yourself in a separate terminal with `uv run prefect server start`. Use `--no-prefect-server` to skip starting a server; Prefect then uses a temporary server that only lives as long as the application.

## Parallel execution

By default, tasks run one after another. FLIMAnalyzer can use [Dask](https://www.dask.org) to run tasks in parallel.

On a *single node*, start a local Dask cluster:

    uv run flimanalyzer -e LocalDaskExecutor --execargs="scheduler=processes,num_workers=8"

As a general guideline, adjust `num_workers` to match the number of CPU cores in your system. Use `scheduler=threads` to run the workers as threads instead of processes.

To use an existing Dask cluster:

    uv run flimanalyzer -e DaskExecutor --execargs="address=tcp://<scheduler-host>:8786"

## How to cite

If you use FLIMAnalyzer, please cite:

1. **The original publication**, in all cases:

   Zhang J, Wallrabe H, Siller K, Mbogo B, Cassidy T, Alam SR, Periasamy A. Measuring metabolic changes in cancer cells using two-photon fluorescence lifetime imaging microscopy and machine-learning analysis. *Journal of Biophotonics* 18(1), e202400426 (2025). [doi:10.1002/jbio.202400426](https://doi.org/10.1002/jbio.202400426)

2. **The publication closest to the version you used**, plus that release's software DOI, from the table below. Use the newest release that is not newer than your version. The version is shown in the FLIMAnalyzer window title.

| Your version | Publication | Software DOI |
|---|---|---|
| v0.5.0 or later | Alam SR, Siller K, Dreicer R, Periasamy A. Label-free optical biomarker for prostate cancer diagnosis. *Molecular Medicine* 32(1), 165 (2026). [doi:10.1186/s10020-026-01605-2](https://doi.org/10.1186/s10020-026-01605-2) | [10.5281/zenodo.23438157](https://doi.org/10.5281/zenodo.23438157) |
| v0.4.1 or earlier | Zhang et al. (2025), the original publication above | [10.5281/zenodo.23426564](https://doi.org/10.5281/zenodo.23426564) |

The concept DOI [10.5281/zenodo.23426563](https://doi.org/10.5281/zenodo.23426563) covers all versions and always resolves to the latest one. Citation metadata is also in [`CITATION.cff`](CITATION.cff); GitHub shows it under "Cite this repository".

## Development

Run the test suite:

    uv sync --extra test
    uv run pytest

Tests that run flows use a temporary Prefect server and database and do not report to any configured server.

Build the documentation (output in `docs/_build/html`):

    uv run --group docs sphinx-build -b html docs docs/_build/html

The `docs` dependency group contains only Sphinx and the lightweight packages needed to document the code; `docs/conf.py` imports `flim` from the source tree and mocks wxPython, PyTorch, Prefect and vistiq. This is also how the documentation is built on Read the Docs (see `.readthedocs.yaml`).
