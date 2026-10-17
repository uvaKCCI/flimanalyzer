# FLIMAnalyzer

Python package for analysis of Fluorescence Lifetime Imaging Microscopy (FLIM) data.

## Requirements

* Python 3.12 or later
* All Python dependencies, including [PyTorch](https://pytorch.org), [Prefect](https://www.prefect.io) and [vistiq](https://github.com/ksiller/vistiq), are declared in `pyproject.toml` and installed automatically.

## Installation

### With uv (recommended)

Clone the repository and let [uv](https://docs.astral.sh/uv/) create the environment. `uv sync` creates `.venv`, installs a matching Python if needed, and installs FLIMAnalyzer in editable mode with the exact package versions from `uv.lock`:

    git clone https://github.com/uvaKCCI/flimanalyzer.git
    cd flimanalyzer
    uv sync

On Windows and Linux (x86_64), uv installs the CUDA build of PyTorch; on macOS the standard PyPI build is used.

To also install the test dependencies:

    uv sync --extra test

### With pip

    git clone https://github.com/uvaKCCI/flimanalyzer.git
    cd flimanalyzer
    python3.12 -m venv .venv
    source .venv/bin/activate    # Windows: .venv\Scripts\activate
    pip install -e .

pip installs the CPU build of PyTorch from PyPI. For GPU support, install PyTorch first by following the instructions at [pytorch.org](https://pytorch.org/get-started/locally/).

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

## Development

Run the test suite:

    uv sync --extra test
    uv run pytest

Tests that run flows use a temporary Prefect server and database and do not report to any configured server.

Build the documentation (output in `docs/_build/html`):

    uv run --group docs sphinx-build -b html docs docs/_build/html

The `docs` dependency group contains only Sphinx and the lightweight packages needed to document the code; `docs/conf.py` imports `flim` from the source tree and mocks wxPython, PyTorch, Prefect and vistiq. This is also how the documentation is built on Read the Docs (see `.readthedocs.yaml`).
