# Batch Mode

`flimbatch` imports data files and runs tools or workflows on them without opening the GUI, for example on a computing cluster or from a script. It takes its settings from an [app settings file](/userguide/settings.md#app-settings-files) saved in the GUI: the import settings and the settings of each tool.

```
flimbatch -i data/ -o results/ -s settings.json --run Summarize --run "Basic FLIRR Analysis"
```

With uv, run it as `uv run flimbatch ...`. `flimanalyzer --batch ...` does the same as `flimbatch ...`. On Windows, use `flimbatch`. There, `flimanalyzer` starts without a console window, so its messages are not shown.

## Steps

1. **Settings:** `flimbatch` reads the app settings file given with `-s`: a path, or the name of a file in the app settings search path (see [App settings files](/userguide/settings.md#app-settings-files)). The file can be from this or an older FLIMAnalyzer version. `flimbatch` uses the file only if every setting in it can be used and checked: it stops with an error if the file can't be read, comes from a newer version, or has invalid values, unknown settings or settings of tools that aren't installed (see [Settings files from older versions](/userguide/settings.md#settings-files-from-older-versions)). Without `-s`, the built-in defaults are used. Environment variables and the other command-line options take precedence over the file (see [Where the settings come from](/userguide/settings.md#where-the-settings-come-from)). `flimbatch` does not read the user settings file, so its results don't depend on settings changed in the GUI.
2. **Import:** it imports the files and folders given with `-i`, the same way as `File` > `Import...`. Only `.txt` and `.csv` files are imported; folders are searched with their subfolders. `-x` leaves out files by their names, for example `-x Results-a-ctrl-1.txt`. The import uses the delimiter, filename parser, and renamed and dropped columns from the settings. If the filters are switched on in the settings (`filters`, `use`), the rows that the `Filter` tool's filters drop are dropped (see [Filtering Data](/userguide/data/filter) and [Filter Tool](/userguide/data/filtertool)). The imported table is saved as the tab-separated file `Imported.txt` in the output folder.
3. **Tools and workflows:** it runs each tool or workflow given with `--run` on the imported table. Each one uses its settings from the settings file, or its defaults if the file has none. If its settings in the file are not valid, the defaults are used, and only the log says so. Most tools need features selected in their settings (at least one, some two; see [Tool dialogs](/userguide/dialogs.md)), and for most tools the defaults select none: without them in the settings file, `flimbatch` stops with an error that names the tool and what is missing, for example `Summarize: features: Select at least 1 feature`. The results of each tool or workflow are saved in a folder named after it, with a folder for each run, named after its date and time, for example `results/Summarize/2026-11-03_14-05-31/` (`-2`, `-3` and so on added if another run started in the same second). The results are saved in the formats of the tool's `autosave` section in the settings file, or tables as tab-separated `.txt` and plots as 300 dpi `.png` if it lists none; whether and where the tool saves (`enabled`, `results_dir`) are not used. That folder also holds a `run_summary.txt` file (see [Saving results](/userguide/dialogs.md#saving-results)).

There is only one imported table, so tools that need two tables, such as `Merge`, can't run in batch mode; `flimbatch` stops with an error message. `Concatenate` gets only the imported table. The workflow `FLIM Feature Analysis` uses the imported table both as training data and as the data to analyze.

When it finishes, `flimbatch` returns the exit code 0 if everything ran, and 1 if a check or a step failed. Scripts can test this code to see whether the run worked.

## Missing columns

Before a workflow runs, its settings are checked against the data (see [Workflows](/userguide/workflows)). A workflow may need a column that the data doesn't have, for example `FAD a1%` when the data has `FAD a1[%]`. In batch mode, this is an error. With `--no-strict`, the closest matching column is used instead, and the run summary lists it under "Notes". This holds when the workflow's `Strict` setting is `Automatic` (the default). With `Strict`: `Yes`, a missing column is always an error; with `Strict`: `No`, it is always guessed (see [Checking the settings](/userguide/workflows.md#checking-the-settings)).

## Options

| Option | |
|---|---|
| `-i`, `--input` | data files or folders (required) |
| `-x`, `--exclude` | files not to import |
| `-o`, `--output` | folder for the results (required). `flimbatch` stops with a message if it can't be reached or written to. |
| `-s`, `--settings` | app settings file: a path, or the name of a file in the app settings search path, with or without `.json` |
| `-r`, `--run` | tool or workflow to run; repeat for several |
| `--strict`, `--no-strict` | workflows: columns that are not in the data are errors (`--strict`, the default in batch mode), or are replaced by the closest matching column (`--no-strict`). A workflow's own `Strict` setting takes precedence. |
| `-e`, `--executor` | where and how the tasks run: `local` (default), `dask-local` or `dask`, with their options, for example `-e local:workers=4`. An unknown name is an error. |
| `--no-prefect-server` | don't start a local Prefect server if none is found; a temporary one is used instead (see [Prefect server](/install/index.md#prefect-server)). |
| `--log-dir` | log folder (`log` > `dir`); default: the output folder (see [Log files](/install/index.md#log-files)) |
| `--cache-dir` | sets the cache folder setting (`cache` > `dir`) |
| `-l`, `--log` | logging level: `debug`, `info` (default), `warning`, `error` or `critical`. The messages are shown in the terminal. |

These options can also be set with environment variables (see [Environment variables](/userguide/settings.md#environment-variables)). An option given on the command line takes precedence.

**Deprecated options.** These options still work, but print a warning that shows the new form:

* `-c`, `--config FILE`: use `-s FILE`.
* `--allow-guesses`: use `--no-strict`.
* The executor names `LocalExecutor`, `LocalDaskExecutor` and `DaskExecutor`: use `local`, `dask-local` and `dask`. `DaskExecutor` without an address starts a Dask cluster on this computer, as `dask-local` does.
* `-a`, `--execargs`: put the options after the executor name, as `-e NAME:KEY=VALUE,...`. `num_workers` is now `workers`. For example, `--execargs="num_workers=4"` becomes `-e local:workers=4`.

The options of the GUI (`flimanalyzer`) are listed in [Command-line options](/install/index.md#command-line-options). The executors and their arguments, and how to run `flimbatch` on an HPC cluster with Slurm, are described in [Concurrent and Distributed Execution](/userguide/execution).

## Running in Docker

The Docker images run `flimbatch` (see [Installing with Docker](/install/index.md#installing-with-docker) for the images). Use `-v` to make the folder with the data and the settings file available inside the container as `/work`:

```
docker run --rm -v "$PWD:/work" ghcr.io/uvakcci/flimanalyzer:latest-cpu \
    -i data/ -o results/ -s settings.json --run Summarize --no-prefect-server
```

- On Linux, add `-u $(id -u)` so that the result files belong to you, not to the image's user.
- With the CUDA image, add `--gpus all` to use the GPU.
- With `--no-prefect-server`, each run uses a temporary Prefect server. To report to a Prefect server instead, give its address with the `docker run` option `-e`, before the image name. For example: `-e PREFECT_API_URL=http://prefect.example.org:4200/api`.
