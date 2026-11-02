# Batch Mode

`flimbatch` imports data files and runs tools or workflows on them without opening the application window, for example on a computing cluster or from a script. It takes its settings from a [settings file](/userguide/settings) saved by the application: the import settings and the settings of each tool.

```
flimbatch -i data/ -o results/ -c settings.json --run Summarize --run "Basic FLIRR Analysis"
```

With uv, run it as `uv run flimbatch ...`. `flimanalyzer --batch ...` does the same as `flimbatch ...`. On Windows, use `flimbatch`. There, `flimanalyzer` starts without a console window, so its messages are not shown.

## Steps

1. **Settings:** `flimbatch` reads the settings file given with `-c`. The file can be from any FLIMAnalyzer version. Without `-c`, the default settings are used.
2. **Import:** it imports the files and folders given with `-i`, the same way as `File` > `Import...`. It uses the delimiter, filename parser, and renamed and dropped columns from the settings, and the range filters if they are switched on. `-x` excludes files. The imported table is saved as `Imported.txt` in the output folder.
3. **Tools and workflows:** it runs each tool or workflow given with `--run` on the imported table. Each one uses its settings from the settings file, or its defaults if the file has none. The results of each tool or workflow are saved in a folder named after it, for example `results/Summarize/`, together with a `run_summary.txt` file.

When it finishes, `flimbatch` returns the exit code 0 if everything ran, and 1 if a check or a step failed. Scripts can test this code to see whether the run worked.

## Missing columns

Before a workflow runs, its settings are checked against the data (see [Workflows](/userguide/workflows)). A workflow may need a column that the data doesn't have, for example `FAD a1%` when the data has `FAD a1[%]`. In batch mode, this is an error. With `--allow-guesses`, the closest matching column is used instead, and the run summary lists it under "Notes".

## Options

| Option | |
|---|---|
| `-i`, `--input` | data files or folders (required) |
| `-x`, `--exclude` | files not to import |
| `-o`, `--output` | folder for the results (required) |
| `-c`, `--settings` | settings file |
| `-r`, `--run` | tool or workflow to run; repeat for several |
| `--allow-guesses` | workflows: for each column not in the data, use the closest matching column |
| `-e`, `--executor` | `LocalExecutor`, `LocalDaskExecutor` or `DaskExecutor` |
| `-a`, `--execargs` | executor arguments, for example `num_workers=4` |
| `--no-prefect-server` | don't start a local Prefect server. Each run uses a temporary one instead. |
| `-l`, `--log` | logging level: `debug`, `info`, `warning` or `error` |

## Installing without the application

Batch mode doesn't need wxPython. To install FLIMAnalyzer without the application, for example on a cluster:

```
uv sync --no-dev           # with uv, in the cloned repository
pip install -e .           # with pip (pip install -e ".[gui]" adds the application)
```

## Docker

The repository's `Dockerfile` builds an image that runs `flimbatch`, without the application. Use `-v` to make the folder with the data and the settings file available inside the container as `/work`:

```
docker build -t flimanalyzer .
docker run --rm -v "$PWD:/work" flimanalyzer \
    -i data/ -o results/ -c settings.json --run Summarize --no-prefect-server
```

On Linux, add `-u $(id -u)` so that the result files belong to you, not to the image's user.

Each release is also published to the GitHub Container Registry:

| Image | |
|---|---|
| `ghcr.io/uvakcci/flimanalyzer:<version>`, `:latest` | with the CUDA build of PyTorch (x86_64, several GB). Use `docker run --gpus all` to use the GPU. |
| `ghcr.io/uvakcci/flimanalyzer:<version>-cpu`, `:latest-cpu` | CPU only (x86_64 and ARM); much smaller |

With `--no-prefect-server`, each run uses a temporary Prefect server. To report to a Prefect server instead, give its address with the `docker run` option `-e`, before the image name. For example: `-e PREFECT_API_URL=http://prefect.example.org:4200/api`.

To build a CPU-only image yourself, or one with Dask support:

```
docker build -t flimanalyzer:cpu --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cpu .
docker build -t flimanalyzer:dask --build-arg EXTRAS=dask .
```
