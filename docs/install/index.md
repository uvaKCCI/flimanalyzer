# Installation

## Requirements

* Python 3.12 or later
* All other Python packages that FLIMAnalyzer needs, including [PyTorch](https://pytorch.org) and [Prefect](https://www.prefect.io), are installed automatically. They are listed in the `pyproject.toml` file of the Git repository [https://github.com/uvaKCCI/flimanalyzer.git](https://github.com/uvaKCCI/flimanalyzer.git).

## Installing from PyPI with uv (recommended)

[uv](https://docs.astral.sh/uv/) creates a virtual environment (a separate Python setup just for FLIMAnalyzer) in the `.venv` folder. If needed, it also installs a matching Python version. Then install FLIMAnalyzer, including its graphical user interface (GUI), into it:
```
uv venv --python 3.12
source .venv/bin/activate    # Windows: .venv\Scripts\activate
uv pip install "flimanalyzer[gui]"
```
The `[gui]` part installs the GUI. Without it, `uv pip install flimanalyzer` installs only what [batch mode](/userguide/batch) needs, for example on a computing cluster. Add `dask` for the optional Dask support (see [Concurrent and distributed execution](/userguide/execution)), e.g. `"flimanalyzer[gui,dask]"`.

## Installing from PyPI with pip

```
python3.12 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install "flimanalyzer[gui]"
```
Conda users can create the Python environment with conda instead of `venv` and install FLIMAnalyzer into it with pip:
```
conda create -n flimenv python=3.12
conda activate flimenv
pip install "flimanalyzer[gui]"
```

## PyTorch and the GPU

Installed from PyPI, FLIMAnalyzer gets PyTorch from PyPI, which provides a different build on each platform:

* **Linux:** the PyPI build includes CUDA, so an NVIDIA GPU is used if its driver is recent enough.
* **Windows:** the PyPI build is CPU-only. To use an NVIDIA GPU, install with `uv pip install "flimanalyzer[gui]" --torch-backend=cu128`, or with pip install the CUDA build first: `pip install torch --index-url https://download.pytorch.org/whl/cu128`. See [pytorch.org](https://pytorch.org/get-started/locally/) for other CUDA versions.
* **macOS:** only Apple Silicon is supported, because current PyTorch versions are not available for Intel Macs. The PyPI build uses the Apple GPU (MPS).

## Installing the latest development version

To install the current state of the Git repository, clone it and let uv create the environment. `uv sync` installs FLIMAnalyzer with the GUI in editable mode, so changes to its code take effect without reinstalling. It uses the exact package versions listed in `uv.lock`, the versions the tests run with. On Windows and Linux (x86_64), it installs the CUDA 12.8 build of PyTorch:
```
git clone https://github.com/uvaKCCI/flimanalyzer.git
cd flimanalyzer
uv sync
```
To install FLIMAnalyzer without the GUI:
```
uv sync --no-group gui
```
With pip, in a virtual environment in the cloned folder:
```
pip install -e ".[gui]"
```

## Installing with Docker

The Docker images run only [batch mode](/userguide/batch). They don't include the GUI. Each release is published to the GitHub Container Registry:

| Image | |
|---|---|
| `ghcr.io/uvakcci/flimanalyzer:<version>`, `:latest` | with the CUDA build of PyTorch (x86_64, several GB) |
| `ghcr.io/uvakcci/flimanalyzer:<version>-cpu`, `:latest-cpu` | CPU only (x86_64 and ARM), much smaller |

```
docker pull ghcr.io/uvakcci/flimanalyzer:latest-cpu
```
To build an image from the repository instead: with the CUDA 12.8 build of PyTorch, with the build for another CUDA version (here 12.6), with the CPU-only build, or with Dask support:
```
docker build -t flimanalyzer .
docker build -t flimanalyzer:cu126 --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu126 .
docker build -t flimanalyzer:cpu --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cpu .
docker build -t flimanalyzer:dask --build-arg EXTRAS=dask .
```
`TORCH_INDEX` replaces PyTorch with the build from that PyTorch package index, in the same PyTorch version (the one in `uv.lock`, currently 2.11.0). Choose the CUDA version that the NVIDIA driver of your computer supports. PyTorch 2.11.0 is available for CUDA 12.6 (`cu126`), 12.8 (`cu128`, the default), 12.9 (`cu129`) and 13.0 (`cu130`).

`EXTRAS=gui` stops the build with an error, because the images do not support a display. To use the GUI, install FLIMAnalyzer with uv or pip.

## Start FLIMAnalyzer with the GUI

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

### Command-line options

| Option | |
|---|---|
| `-i`, `--input` | data files to open at startup, each in its own table window |
| `-c`, `--config` | settings file to start with, instead of `defaults.json` (see [Settings](/userguide/settings)) |
| `-l`, `--log` | logging level: `debug`, `info` (default), `warning`, `error` or `critical` |
| `--no-prefect-server` | don't start a local Prefect server if none is found (see [Prefect server](#prefect-server)) |
| `-e`, `--executor` | where the tasks run: `LocalExecutor` (default), `LocalDaskExecutor` or `DaskExecutor` (see [Concurrent and Distributed Execution](/userguide/execution)) |
| `-a`, `--execargs` | executor options, for example `num_workers=4` |
| `--batch` | runs [batch mode](/userguide/batch) instead of the GUI: `flimanalyzer --batch ...` does the same as `flimbatch ...` |

The GUI writes its messages to the log file `flimanalyzer.log`, in the folder it was started from. The file is replaced each time FLIMAnalyzer starts. When an error message says "see the log", the details are in this file.

## Using a GPU

The autoencoder tools have a `Device` setting. These tools are `Autoencoder: Train`, `Autoencoder: Run` and `Autoencoder: Augment Data`, and the workflows `FLIM Data Augmentation Tuning` and `FLIM Feature Analysis`. The `Device` setting chooses which processor does the calculations, in the GUI and in batch mode:

* `auto` (default): uses an NVIDIA GPU (`cuda`) if there is one, otherwise the Apple GPU (`mps`), otherwise the CPU.
* `cpu`, `cuda` or `mps`: uses that device, or the CPU if the device is not available.

Which GPU can be used depends on the PyTorch build that was installed (see above). Trained models are saved so that they don't need a GPU, so a model trained on a GPU can also be used on a computer without one.

## Prefect server

FLIMAnalyzer runs tools and workflows as [Prefect](https://www.prefect.io) flows. A Prefect server records these runs. At startup, the GUI and `flimbatch` look for a Prefect server in this order:

1. The server set in the active Prefect profile or in the `PREFECT_API_URL` environment variable, if it responds.
2. A server already running on this computer at `http://127.0.0.1:4200/api`.
3. If there is none, FLIMAnalyzer starts a local server (`prefect server start`) and stops it again when FLIMAnalyzer closes. The server's messages are added to the file `prefect-server.log` in the folder FLIMAnalyzer was started from.

With `--no-prefect-server`, step 3 is skipped: if no server is found, Prefect uses a temporary server that runs only as long as FLIMAnalyzer (or `flimbatch`) runs.

The Prefect UI shows the flow and task runs of a server in the web browser, for example at [http://127.0.0.1:4200](http://127.0.0.1:4200) for a local server. The progress dialog links to each run there (see [The progress dialog](/userguide/workflows.md#the-progress-dialog)). To keep a local server running between sessions, start it yourself in a separate terminal with `uv run prefect server start` (or `prefect server start` in an activated environment).

### Using another Prefect server

To report the runs to a Prefect server on another computer, set its address in a Prefect profile. A profile is a named set of Prefect settings ([Settings and profiles](https://www.prefect.io/docs/v3/develop/settings-and-profiles) in the Prefect documentation). In the environment FLIMAnalyzer is installed in:

```
prefect profile create flim-server
prefect profile use flim-server
prefect config set PREFECT_API_URL=http://prefect.example.org:4200/api
```

`prefect profile use` makes the profile the active one; FLIMAnalyzer then uses this server. `prefect profile use default` switches back. Instead of a profile, you can also set the environment variable `PREFECT_API_URL`; environment variables take precedence over the profile ([Prefect settings](https://www.prefect.io/docs/v3/concepts/settings-and-profiles)).

If the server is self-hosted and protected with basic authentication, also set the user name and password, separated by a colon ([Security settings](https://www.prefect.io/docs/v3/advanced/security-settings)):

```
prefect config set PREFECT_API_AUTH_STRING="admin:password"
```

`PREFECT_API_KEY` is used only for Prefect Cloud; `prefect cloud login` sets it together with `PREFECT_API_URL`.

If the server set in the profile doesn't respond, FLIMAnalyzer writes a warning to the log and goes on with steps 2 and 3 above.
