# Installation

## Requirements

* Python 3.12 to 3.14
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
* **Windows:** the PyPI build is CPU-only. To use an NVIDIA GPU, install with `uv pip install "flimanalyzer[gui]" --torch-backend=cu130`, or with pip install the CUDA build first: `pip install torch --index-url https://download.pytorch.org/whl/cu130`. See [pytorch.org](https://pytorch.org/get-started/locally/) for other CUDA versions.
* **macOS:** only Apple Silicon is supported, because current PyTorch versions are not available for Intel Macs. The PyPI build uses the Apple GPU (MPS).

**Older NVIDIA GPUs.** The CUDA 13.0 build of PyTorch, which the installs from the source and the Docker CUDA image use, needs NVIDIA driver 580 or newer and a GPU of the Turing generation or newer (e.g. T4, RTX 20xx, A100, H100). For older GPUs such as the V100, use the CUDA 12.6 build (`cu126`) of the same PyTorch version, 2.14.1:

* Installed from PyPI with uv: `uv pip install "flimanalyzer[gui]" --torch-backend=cu126`. With pip, install the CUDA 12.6 build first: `pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126`.
* Installed from the source (`uv sync`, see [Installing the latest development version](#installing-the-latest-development-version)): replace PyTorch after `uv sync` with `uv pip install --reinstall torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126`. A later `uv sync` installs the CUDA 13.0 build again.
* Docker: build the image with `--build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu126` (see [Installing with Docker](#installing-with-docker)).

Check PyTorch's release notes for the GPUs each build supports.

## Installing the latest development version

To install the current state of the Git repository, clone it and let uv create the environment. `uv sync` installs FLIMAnalyzer with the GUI in editable mode, so changes to its code take effect without reinstalling. It uses the exact package versions listed in `uv.lock`, the versions the tests run with. On Windows and Linux (x86_64), it installs the CUDA 13.0 build of PyTorch:
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
To build an image from the repository instead: with the CUDA 13.0 build of PyTorch, with the build for another CUDA version (here 12.6, for older GPUs), with the CPU-only build, or with Dask support:
```
docker build -t flimanalyzer .
docker build -t flimanalyzer:cu126 --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu126 .
docker build -t flimanalyzer:cpu --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cpu .
docker build -t flimanalyzer:dask --build-arg EXTRAS=dask .
```
`TORCH_INDEX` replaces PyTorch with the build from that PyTorch package index, in the same PyTorch version (the one in `uv.lock`, currently 2.14.1). Choose the CUDA version that the NVIDIA driver and the GPU of your computer support. PyTorch 2.14.1 is available for CUDA 12.6 (`cu126`), 13.0 (`cu130`, the default) and 13.2 (`cu132`). CUDA 13 needs NVIDIA driver 580 or newer and a GPU of the Turing generation or newer (e.g. T4, RTX 20xx, A100, H100). For older GPUs such as the V100, try the CUDA 12.6 build (`cu126`); check PyTorch's release notes for the GPUs it supports.

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

(command-line-options)=
**Command-line options**

```{tabularcolumns} >{\raggedright\arraybackslash}\Y{0.32}>{\raggedright\arraybackslash}\Y{0.68}
```

| Option | |
|---|---|
| `-i`, `--input` | data files or folders to open at startup (takes several values, and can be repeated: `-i a.txt -i b.txt`), each file in its own table window, read with the settings of `Open Tables`; with `--run`, the files to run it on (`--run "Import Tables"` shows its dialog for them) |
| `-x`, `--exclude` | files not to read, by their exact file name. Takes several values, and can be repeated: `-x a.txt -x b.txt` |
| `-r`, `--run` | tool or workflow to run on the `-i` files at startup: a name, or a workflow file or tool file (a path, or a file name ending in `.json` in the workflow search path). A workflow file's steps are shown, then it runs; a tool file runs as a workflow of one step; a tool given by name opens its dialog with the files' tables. Repeat it for several runs; they run in the order given. |
| `-w`, `--workflow-path` | folders searched for workflow files and tool files. They replace the folders of `FLIM_WORKFLOW_PATH` and of `workflow_paths` in the user settings file (see [Where workflow files are found](/userguide/workflows.md#where-workflow-files-are-found)). Takes several values, and can be repeated. |
| `-s`, `--settings` | app settings file for this session: a path, or the name of a file in the app settings search path, with or without `.json` (see [Settings](/userguide/settings.md#app-settings-files)) |
| `-o`, `--output` | results folder: the folder under `Save results` for tools that have no folder of their own |
| `-e`, `--executor` | where and how the tasks run: `local` (default), `dask-local` or `dask`, with their options, for example `-e local:workers=4` (see [Concurrent and Distributed Execution](/userguide/execution)) |
| `--prefect-server`, `--no-prefect-server` | `--prefect-server` (the default) uses a local Prefect server, and starts one if none is found. `--no-prefect-server` uses a temporary Prefect server for each run instead (see [Prefect server](#prefect-server)). |
| `--server-timeout SECONDS` | how long to wait for responses of the Prefect server, and of the Dask cluster if one is used (default: 60). Below 60, a local Prefect server that is started may not be ready in time. |
| `--log-dir` | log folder (`log` > `dir`; see [Log files](#log-files)) |
| `-l`, `--log-level` | logging level: `debug`, `info` (default), `warning`, `error` or `critical`; also `--log` |

`-o`, `-e`, `--prefect-server`, `--server-timeout`, `--log-dir` and `-l` can also be set with environment variables (`FLIM_RESULTS_DIR`, `FLIM_EXECUTION`, `FLIM_PREFECT_SERVER`, `FLIM_SERVER_TIMEOUT`, `FLIM_LOG_DIR`, `FLIM_LOG_LEVEL`; see [Environment variables](/userguide/settings.md#environment-variables)), and, except `-l`, in an app settings file (see [Settings](/userguide/settings.md#where-the-settings-come-from)); `-w` with `FLIM_WORKFLOW_PATH`. The other options have no environment variable. An option given on the command line takes precedence.

**Deprecated options.** These options still work, but print a warning that shows the new form:

```{tabularcolumns} >{\raggedright\arraybackslash}\Y{0.20}>{\raggedright\arraybackslash}\Y{0.24}>{\raggedright\arraybackslash}\Y{0.45}>{\raggedright\arraybackslash}\Y{0.11}
```

| Deprecated | Use instead | Example | Removed in |
|---|---|---|---|
| `-c`, `--config FILE` | `-s`, `--settings FILE` | `-c settings.json` → `-s settings.json` | 0.8.0 |
| `--batch` | `flimbatch` with the same arguments | `flimanalyzer --batch -i data/ -o results/ ...` → `flimbatch -i data/ -o results/ ...` | 0.8.0 |
| `-e LocalExecutor`, `LocalDaskExecutor`, `DaskExecutor` | `-e local`, `dask-local`, `dask` | `-e LocalDaskExecutor` → `-e dask-local` | 1.0.0 |
| `-a`, `--execargs` | the options after the executor name: `-e NAME:KEY=VALUE,...`; `num_workers` is now `workers` | `-e LocalDaskExecutor --execargs="scheduler=processes,num_workers=8"` → `-e dask-local:workers=8,scheduler=processes` | 0.8.0 |

`DaskExecutor` without an address starts a Dask cluster on this computer, as `dask-local` does.

## Log files

FLIMAnalyzer writes its messages to a log file. When an error message says "see the log", the details are in this file. A file is never overwritten:

* Each session of the GUI gets its own file, named after the program, its start time and its process ID, for example `flimanalyzer_2026-11-09T14-23-43_12345.log`.
* Each call of `flimbatch` writes `flimbatch.log` into its results folder, `<output>/<date and time>/` (see [Results](/userguide/batch.md#results)). If a log folder is set (items 1 to 3 below), the file is in that folder instead, named after the call's start and its process ID, for example `flimbatch_2026-11-09T14-23-43_12345.log`. A dry run (`--dry-run`) writes a file of this name into the output folder (`-o`), or into the log folder if one is set.

The location of the log file is determined in this order; the first that applies is used:

1. The folder given with `--log-dir`.
2. The folder in the environment variable `FLIM_LOG_DIR`, for example set in your shell profile or in a cluster job script: `export FLIM_LOG_DIR=/scratch/$USER/flimanalyzer-logs`.
3. The folder in `log` > `dir` of the app settings file given with `-s`, or, for the GUI, of the user settings file (see [Settings](/userguide/settings.md#where-the-settings-come-from)).
4. For the GUI, the platform's log folder:
   * macOS: `~/Library/Logs/FLIMAnalyzer`
   * Linux: `~/.local/state/FLIMAnalyzer/log`
   * Windows: `%LOCALAPPDATA%\FLIMAnalyzer\Logs`
5. For `flimbatch`, the results folder of the call, as `flimbatch.log`. `flimbatch` also writes its messages to the terminal.

If the log folder can't be created or written to, the log goes to the folder `FLIMAnalyzer` in the system's temporary folder, and FLIMAnalyzer says so. The Settings dialog of the GUI shows the log file in use (`File` > `Settings...`).

A log file that reaches 10 MB is renamed with `.1` added (`.2`, `.3` for older parts; up to three are kept), and a new one is started. When the GUI starts, it removes the log files in its log folder that are older than 30 days; `log` > `max_age_days` in an app settings file sets another number of days. It removes only files named like FLIMAnalyzer's log files. `flimbatch` doesn't remove logs, because its log is usually in a results folder.

`-l` (`--log-level`) sets the level of the messages written, for FLIMAnalyzer and for the libraries it uses. Each message names where it comes from, for example `flim.core.runner` or `matplotlib`.

## Using a GPU

The autoencoder tools and workflows have a `Device` setting: the tools `Autoencoder Run` and `Autoencoder Augment Data`, and the workflows `Autoencoder Train`, `FLIM Data Augmentation Tuning` and `FLIM Feature Analysis`. The `Device` setting selects the hardware they compute on: a GPU (graphics processor) or the CPU. This applies to both the GUI and batch mode. The choices are:

* `auto` (default): uses an NVIDIA GPU (`cuda`) if there is one, otherwise the Apple GPU (`mps`), otherwise the CPU.
* `cpu`, `cuda` or `mps`: uses that device, or the CPU if the device is not available.

Which GPU can be used depends on the PyTorch build that was installed (see above). Trained models are saved so that they don't need a GPU, so a model trained on a GPU can also be used on a computer without one.

## Prefect server

FLIMAnalyzer runs tools and workflows as [Prefect](https://www.prefect.io) flows. A Prefect server records these runs. At startup, the GUI and `flimbatch` look for a Prefect server in this order:

1. The server set in the active Prefect profile or in the `PREFECT_API_URL` environment variable, if it responds.
2. A server already running on this computer at `http://127.0.0.1:4200/api`.
3. If there is none, FLIMAnalyzer starts a local server (`prefect server start`) and stops it again when FLIMAnalyzer closes. If port 4200 is taken, the server is started on a free port. The server's messages are added to the file `prefect-server.log` in the folder FLIMAnalyzer was started from. If no server can be started, FLIMAnalyzer stops with an error that names this file.

The server found or started at startup is used for all runs until FLIMAnalyzer closes. If it no longer responds before a run, for example because another FLIMAnalyzer process that started it has closed, a server is found or started again in the same order, and used for this and the next runs.

With `--no-prefect-server`, step 3 is skipped: if no server is found, Prefect starts a temporary server for each run, which stops when the run ends.

The Prefect UI shows the flow and task runs of a server in the web browser, for example at [http://127.0.0.1:4200](http://127.0.0.1:4200) for a local server. `Monitor` > `Prefect Server` opens it, and `Monitor` > `Last Run` opens the page of the last run the GUI started. The progress dialog links to each run there (see [The progress dialog](/userguide/workflows.md#the-progress-dialog)). Each task run shows the settings its tool ran with in its `Artifacts` tab, as JSON. Each flow run shows, in its `Artifacts` tab, the versions of FLIMAnalyzer, Python and the main packages, how its tasks ran (threads or Dask, with their settings), and the files its tables were read from. The `Logs` tab of a run also shows FLIMAnalyzer's messages from that run, for example a tool's warnings, except those of tasks that Dask runs in other processes. No data values are sent to the server. To keep a local server running between sessions, start it yourself in a separate terminal with `uv run prefect server start` (or `prefect server start` in an activated environment).

**Using another Prefect server**

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
