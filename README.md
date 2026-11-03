# <img src="flim/resources/flimanalyzer.png" alt="" width="80" align="top"> FLIMAnalyzer

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://github.com/uvaKCCI/flimanalyzer/blob/main/pyproject.toml) [![Tests](https://github.com/uvaKCCI/flimanalyzer/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/uvaKCCI/flimanalyzer/actions/workflows/tests.yml) [![codecov](https://codecov.io/gh/uvaKCCI/flimanalyzer/branch/main/graph/badge.svg)](https://codecov.io/gh/uvaKCCI/flimanalyzer) [![Documentation Status](https://readthedocs.org/projects/flimanalyzer/badge/?version=latest)](https://flimanalyzer.readthedocs.io/en/latest/) [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23426563.svg)](https://doi.org/10.5281/zenodo.23426563)

Python package for analysis of Fluorescence Lifetime Imaging Microscopy (FLIM) data.

Documentation: https://flimanalyzer.readthedocs.io

## Requirements

* Python 3.12 or later
* All Python dependencies, including [PyTorch](https://pytorch.org) and [Prefect](https://www.prefect.io), are declared in `pyproject.toml` and installed automatically.

## Installation

### With uv (recommended)

Clone the repository and let [uv](https://docs.astral.sh/uv/) create the environment. `uv sync` creates `.venv`, installs a matching Python if needed, and installs FLIMAnalyzer with its graphical user interface (GUI) in editable mode, with the exact package versions from `uv.lock`:

    git clone https://github.com/uvaKCCI/flimanalyzer.git
    cd flimanalyzer
    uv sync

On Windows and Linux (x86_64), uv installs the CUDA 12.8 build of PyTorch, so an NVIDIA GPU can be used. On macOS, the PyPI build is used, which can use the Apple GPU (MPS). Only Macs with Apple Silicon are supported, because current PyTorch versions are not available for Intel Macs.

To install FLIMAnalyzer without the GUI, for example for [batch mode](#run-flimanalyzer-in-batch-mode) on a computing cluster:

    uv sync --no-group gui

To also install the test dependencies, or the optional Dask support (see [Concurrent and distributed execution](#concurrent-and-distributed-execution)):

    uv sync --extra test
    uv sync --extra dask

### With pip

    git clone https://github.com/uvaKCCI/flimanalyzer.git
    cd flimanalyzer
    python3.12 -m venv .venv
    source .venv/bin/activate    # Windows: .venv\Scripts\activate
    pip install -e ".[gui]"

The `gui` extra installs the graphical user interface (GUI). Without it, `pip install -e .` installs only what [batch mode](#run-flimanalyzer-in-batch-mode) needs.

pip installs PyTorch from PyPI, which provides a different build on each platform:

* **Linux:** the PyPI build includes CUDA, so an NVIDIA GPU is used if its driver is recent enough.
* **Windows:** the PyPI build is CPU-only. For an NVIDIA GPU, install the CUDA build before FLIMAnalyzer, for example `pip install torch --index-url https://download.pytorch.org/whl/cu128`. See [pytorch.org](https://pytorch.org/get-started/locally/) for other CUDA versions.
* **macOS:** only Apple Silicon is supported. The PyPI build uses the Apple GPU (MPS).

### With Docker

The Docker images run only [batch mode](#run-flimanalyzer-in-batch-mode). They don't include the GUI. Each release is published to the GitHub Container Registry:

| Image | |
|---|---|
| `ghcr.io/uvakcci/flimanalyzer:<version>`, `:latest` | with the CUDA build of PyTorch (x86_64, several GB) |
| `ghcr.io/uvakcci/flimanalyzer:<version>-cpu`, `:latest-cpu` | CPU only (x86_64 and ARM), much smaller |

    docker pull ghcr.io/uvakcci/flimanalyzer:latest-cpu

To build an image from the repository instead: with the CUDA 12.8 build of PyTorch, with the build for another CUDA version (here 12.6), with the CPU-only build, or with Dask support:

    docker build -t flimanalyzer .
    docker build -t flimanalyzer:cu126 --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu126 .
    docker build -t flimanalyzer:cpu --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cpu .
    docker build -t flimanalyzer:dask --build-arg EXTRAS=dask .

`TORCH_INDEX` replaces PyTorch with the build from that PyTorch package index, in the same PyTorch version (the one in `uv.lock`, currently 2.11.0). Choose the CUDA version that the NVIDIA driver of your computer supports. PyTorch 2.11.0 is available for CUDA 12.6 (`cu126`), 12.8 (`cu128`, the default), 12.9 (`cu129`) and 13.0 (`cu130`).

`EXTRAS=gui` stops the build with an error, because the images do not support a display.

## Start FLIMAnalyzer with the GUI

With uv, no activation is needed:

    uv run flimanalyzer

In an activated environment:

    flimanalyzer

To open data files (tab- or comma-separated) right away, each in its own window:

    uv run flimanalyzer -i results.txt more-results.csv

Run `flimanalyzer --help` for all command line options.

## Using a GPU

The autoencoder tools (Autoencoder: Train, Run and Augment Data, and the FLIM Data Augmentation Tuning and FLIM Feature Analysis workflows) have a **Device** setting, in the GUI and in batch mode:

* `auto` (default): an NVIDIA GPU (`cuda`) if available, otherwise the Apple GPU (`mps`), otherwise the CPU.
* `cpu`, `cuda` or `mps`: uses that device, or the CPU if it is not available.

Which GPU can be used depends on the PyTorch build that was installed (see [Installation](#installation)). Trained models are saved so that they don't need a GPU, so a model trained on a GPU can also be used on a computer without one.

## Run FLIMAnalyzer in batch mode

`flimbatch` imports data files and runs tools or workflows on them without opening the GUI, for example on a computing cluster. It takes its settings from a settings file saved in the GUI (File > Export Settings...): the import settings and the settings of each tool. A tool's dialog can add its settings to such a file with Save Settings..., which keeps the file's other sections. Load Settings... reads the tool's own section back.

    uv run flimbatch -i data/ -o results/ -c settings.json \
        --run Summarize --run "Basic FLIRR Analysis"

The imported table is saved as `results/Imported.txt`, and each tool's results in `results/<tool name>/`. A workflow column that is not in the data (for example `FAD a1%` for `FAD a1[%]`) is an error. `--allow-guesses` uses the closest column instead and lists it in the run summary. The exit code is 1 if a check or task failed. Run `flimbatch --help` for all options.

`flimanalyzer --batch …` does the same as `flimbatch …`. On Windows, use `flimbatch`: `flimanalyzer` starts without a console there, so its messages are not shown.

### In Docker

The image runs `flimbatch`. Make the folder with the data and the settings file available inside the container as `/work`:

    docker run --rm -v "$PWD:/work" ghcr.io/uvakcci/flimanalyzer:latest-cpu \
        -i data/ -o results/ -c settings.json --run Summarize --no-prefect-server

* On Linux, add `-u $(id -u)` so that the result files belong to you.
* With the CUDA image, add `--gpus all` to use the GPU.
* With `--no-prefect-server`, each run uses a temporary Prefect server. To report to a Prefect server instead, pass its address, for example `-e PREFECT_API_URL=http://prefect.example.org:4200/api`.

## Prefect server

FLIMAnalyzer runs analyses and workflows as [Prefect](https://www.prefect.io) flows. At startup it looks for a Prefect server in this order:

1. The server configured in the active Prefect profile or in the `PREFECT_API_URL` environment variable, e.g.

       prefect profile use <profile>
       # or
       export PREFECT_API_URL=https://my-prefect-server/api

2. A server already running locally at `http://127.0.0.1:4200/api`.
3. If none is found, FLIMAnalyzer starts a local server (`prefect server start`) and stops it again when FLIMAnalyzer closes. The server's output is written to `prefect-server.log`.

Flow and task runs can be inspected in the Prefect UI of the server in use, e.g. [http://127.0.0.1:4200](http://127.0.0.1:4200) for a local server. To keep a local server running across sessions, start it yourself in a separate terminal with `uv run prefect server start`. Use `--no-prefect-server` to skip starting a server; Prefect then uses a temporary server that only runs as long as FLIMAnalyzer.

## Concurrent and distributed execution

Every tool and workflow step runs as a Prefect task. A task starts as soon as the results it needs are ready. Tasks that don't depend on each other run concurrently, without waiting for each other. Tasks that draw figures take turns, because matplotlib's pyplot is not thread-safe.

By default, up to one task per CPU core runs at a time, as threads. To change that number:

    uv run flimanalyzer --execargs="num_workers=4"

`num_workers=1` runs one task at a time. Prefect's `PREFECT_TASKS_RUNNER_THREAD_POOL_MAX_WORKERS` setting, if set, is used as the default.

FLIMAnalyzer can also use [Dask](https://www.dask.org). Dask support is optional; install it with `uv sync --extra dask` (or `pip install -e ".[dask]"`).

On a *single node*, start a local Dask cluster:

    uv run flimanalyzer -e LocalDaskExecutor --execargs="scheduler=processes,num_workers=8"

As a general guideline, adjust `num_workers` to match the number of CPU cores in your system. Use `scheduler=threads` to run the workers as threads instead of processes.

To use an existing Dask cluster:

    uv run flimanalyzer -e DaskExecutor --execargs="address=tcp://<scheduler-host>:8786"

### Concurrency limits

Each task is tagged: with the tool's name when a single tool runs (e.g. `Autoencoder: Train`), and with the step's tags in a workflow. Prefect applies [tag concurrency limits](https://docs.prefect.io/v3/develop/task-run-limits) set on the Prefect server to these tasks, whichever executor is used. For example, to let only one autoencoder training run at a time:

    uv run prefect concurrency-limit create "Autoencoder: Train" 1

`uv run prefect concurrency-limit ls` lists the limits, and `uv run prefect concurrency-limit delete <tag>` removes one.

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

The tests run one after another. The GUI tests depend on wxPython's event loop and on timing, so they must not run in parallel. Only the core tests (no GUI) can run in parallel, one process per CPU core, with `pytest-xdist`:

    uv run pytest -n auto tests/core

Build the documentation (output in `docs/_build/html`):

    uv run --group docs sphinx-build -b html docs docs/_build/html

The `docs` dependency group contains only Sphinx and the lightweight packages needed to document the code; `docs/conf.py` imports `flim` from the source tree and mocks wxPython, PyTorch and Prefect. This is also how the documentation is built on Read the Docs (see `.readthedocs.yaml`).
