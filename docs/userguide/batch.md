# Batch Mode

`flimbatch` imports data files and runs tools or workflows on them without the application, for example on a cluster or in a script. It uses a [settings file](/userguide/settings) saved by the application: its import settings, and the settings of each tool.

```
flimbatch -i data/ -o results/ -c settings.json --run Summarize --run "Basic FLIRR Analysis"
```

With uv, run it as `uv run flimbatch ...`. `flimanalyzer --batch ...` does the same as `flimbatch ...`. On Windows, use `flimbatch`: `flimanalyzer` starts without a console there, so its messages are not shown.

## Steps

1. **Settings:** reads the settings file given with `-c` (saved by any FLIMAnalyzer version). Without `-c`, the defaults are used.
2. **Import:** imports the files and folders given with `-i` as `File` > `Import...` does, with the delimiter, filename parser, renamed and dropped columns, and the range filters if they are used. `-x` excludes files. The imported table is saved as `Imported.txt` in the output folder.
3. **Tools and workflows:** runs each `--run` tool or workflow on the imported table, with its settings from the settings file (or its defaults). The results of each are saved in a folder named after it, e.g. `results/Summarize/`, with a `run_summary.txt`.

The exit code is 0 if everything ran, and 1 if a check or a step failed, so scripts can test it.

## Missing columns

Workflows are checked against the data before they run (see [Workflows](/userguide/workflows)). In batch mode, a column that the workflow needs but the data doesn't have, for example `FAD a1%` when the data has `FAD a1[%]`, is an error. `--allow-guesses` uses the closest column instead; the run summary lists it under "Notes".

## Options

| Option | |
|---|---|
| `-i`, `--input` | data files or folders (required) |
| `-x`, `--exclude` | files not to import |
| `-o`, `--output` | folder for the results (required) |
| `-c`, `--settings` | settings file |
| `-r`, `--run` | tool or workflow to run; repeat for several |
| `--allow-guesses` | workflows: use the closest columns for columns not in the data |
| `-e`, `--executor` | `LocalExecutor`, `LocalDaskExecutor` or `DaskExecutor` |
| `-a`, `--execargs` | executor arguments, e.g. `num_workers=4` |
| `--no-prefect-server` | don't start a local Prefect server; each run uses a temporary one |
| `-l`, `--log` | logging level: `debug`, `info`, `warning` or `error` |

## Installing without the application

Batch mode doesn't need wxPython. To install FLIMAnalyzer without the application, e.g. on a cluster:

```
uv sync --no-dev           # with uv, in the cloned repository
pip install -e .           # with pip (pip install -e ".[gui]" adds the application)
```

## Docker

The repository's `Dockerfile` builds an image that runs `flimbatch`, without the application. Mount the folder with the data and the settings file as `/work`:

```
docker build -t flimanalyzer .
docker run --rm -v "$PWD:/work" flimanalyzer \
    -i data/ -o results/ -c settings.json --run Summarize --no-prefect-server
```

On Linux, add `-u $(id -u)` so the results belong to you rather than to the image's user.

Each release is also published to the GitHub Container Registry:

| Image | |
|---|---|
| `ghcr.io/uvakcci/flimanalyzer:<version>`, `:latest` | with the CUDA build of PyTorch (x86_64; several GB). Use `docker run --gpus all` for the GPU. |
| `ghcr.io/uvakcci/flimanalyzer:<version>-cpu`, `:latest-cpu` | CPU only (x86_64 and ARM); much smaller |

With `--no-prefect-server`, each run uses a temporary Prefect server. To report to a Prefect server instead, pass its address, e.g. `-e PREFECT_API_URL=http://prefect.example.org:4200/api` (a `docker run` option, before the image name).

To build a CPU-only image yourself, or one with Dask support:

```
docker build -t flimanalyzer:cpu --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cpu .
docker build -t flimanalyzer:dask --build-arg EXTRAS=dask .
```
