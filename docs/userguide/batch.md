# Batch Mode

`flimbatch` reads data files and runs tools or workflows on them without opening the GUI, for example on a computing cluster or from a script. A [workflow file](/userguide/workflows.md#workflow-files) says exactly what a run does with the files; tools run with their settings from an [app settings file](/userguide/settings.md#app-settings-files) saved in the GUI.

```
flimbatch -i data/ -o results/ --run Import
flimbatch -i data/ -o results/ --workflow my-analysis.json
flimbatch -i data/ -o results/ -s settings.json --run Summarize
```

With uv, run it as `uv run flimbatch ...`. `flimanalyzer --batch ...` does the same as `flimbatch ...`. On Windows, use `flimbatch`. There, `flimanalyzer` starts without a console window, so its messages are not shown.

## Steps

1. **Settings:** `flimbatch` reads the app settings file given with `-s`: a path, or the name of a file in the app settings search path (see [App settings files](/userguide/settings.md#app-settings-files)). The file can be from this or an older FLIMAnalyzer version. `flimbatch` uses the file only if every setting in it can be used and checked: it stops with an error if the file can't be read, comes from a newer version, or has invalid values, unknown settings or settings of tools that aren't installed (see [Settings files from older versions](/userguide/settings.md#settings-files-from-older-versions)). Without `-s`, the built-in defaults are used. Environment variables and the other command-line options take precedence over the file (see [Where the settings come from](/userguide/settings.md#where-the-settings-come-from)). `flimbatch` does not read the user settings file, so its results don't depend on settings changed in the GUI, and it writes no settings file, so a run never changes what the GUI starts with.
2. **Reading:** it reads each file given with `-i` into a table of its own, with the columns `Source` (the file as a URI), `Directory` and `File` added (see [The Source column](/userguide/data/load.md#the-source-column)). Folders are searched with their subfolders for the files with the extensions of `Files to include` in the read settings (default: `.txt` and `.csv`). `-x` leaves out files by their names, for example `-x Results-a-ctrl-1.txt`. Nothing else is done to the data: renaming, dropping and calculating columns, categories from the file names and joining the files into one table are steps of a workflow, for example of the built-in `Import` workflow. The files are read with the settings of the `Open Tables` tool in the settings file (see [Read settings](/userguide/data/load.md#read-settings)); without them, tab and comma separate columns. `--run "Import Tables"` reads them with the settings of `Import Tables` instead, and runs the workflow they name (`workflow`), so one settings file describes the whole run. By default, they name no workflow: then `--run "Import Tables"` stops with an error. A file that can't be read is skipped with a warning.
3. **Tools and workflows:** it runs each tool or workflow given with `--run` or `--workflow` on the tables. A workflow file runs as its steps say: each step once per table, until a step such as `Concatenate` joins the tables into one (see [Workflow files](/userguide/workflows.md#workflow-files)). `--run` with a tool runs it once on each table, or, for a tool that takes several tables such as `Concatenate`, once on all of them. `--run` with a workflow made in code, such as `Basic FLIRR Analysis`, runs it once on each table. Each tool or such workflow uses its settings from the settings file, or its defaults if the file has none. Most tools need features selected in their settings (at least one, some two; see [Tool dialogs](/userguide/dialogs.md)), and for most tools the defaults select none: without them in the settings file, `flimbatch` stops with an error that names the tool and what is missing, for example `Summarize: features: Select at least 1 feature`. The results of each tool or workflow are saved in a folder named after it, with a folder for each run, named after its date and time, for example `results/Summarize/2026-11-03_14-05-31/` (`-2`, `-3` and so on added if another run started in the same second). A workflow made in code that runs on several tables saves each table's run in a folder of its own: `<output>/<workflow name>/<table>/<date and time>/`. The results are saved in the formats of the tool's `autosave` section in the settings file, or tables as tab-separated `.txt` and plots as 300 dpi `.png` if it lists none; whether and where the tool saves (`enabled`, `results_dir`) are not used. That folder also holds a `run_summary.txt` file (see [Saving results](/userguide/dialogs.md#saving-results)). A workflow file's run saves only the results of the steps marked `save`, in the formats of its `autosave` section. Each run's folder also holds `resolved.json`: the run's settings with every setting stated, as a workflow file (or, for a workflow made in code, a tool file). It states every setting of every step, the formats of each kind of result, and the columns the run used where the settings leave them to the data (`features: all`, guessed columns, skipped entries). Run it with `--run resolved.json` on the same files to repeat the run, also with a later FLIMAnalyzer version whose defaults changed. `flimsettings workflow --resolve FILE` and `flimsettings tool --resolve FILE` show a file with every setting stated before a run.

Tools that need two tables, such as `Merge`, can't run with `--run`; use them in a workflow file. The workflow `FLIM Feature Analysis` uses each table both as training data and as the data to analyze.

`flimbatch` needs at least one `--run` or `--workflow`. To read the files into one table, run the built-in `Import` workflow: `--run Import`. It also renames the channels' columns and drops the other channels' columns, and it calculates the FLIM features (see [Import Tables](/userguide/data/load.md#import-tables)).

## Validating a run first

With `--dry-run`, `flimbatch` reads only the first rows of each file, validates every run against them (the tools' settings and, for a workflow file, every step against the columns it gets), reports what it found and runs nothing. `-o` is not needed. The exit code is 0 if no check found an error, else 1.

When it finishes, `flimbatch` returns the exit code 0 if everything ran, and 1 if a validation or a step failed. Scripts can test this code to see whether the run worked.

## Missing columns

Before a workflow runs, its settings are validated against the data (see [Workflows](/userguide/workflows)). A workflow may need a column that the data doesn't have, for example `FAD a1%` when the data has `FAD a1[%]`. This is an error, unless the tool file or the workflow file allows guesses or skipped entries in its `processing` section: `"processing": {"strict": false}` uses the closest matching column, and the run summary lists it under "Notes" (see `processing` under [Workflow files](/userguide/workflows.md#workflow-files)).

## Options

| Option | |
|---|---|
| `-i`, `--input` | data files or folders (required) |
| `-x`, `--exclude` | files not to read (names) |
| `-o`, `--output` | folder for the results (required, except with `--dry-run`). `flimbatch` stops with a message if it can't be reached or written to. |
| `-s`, `--settings` | app settings file: a path, or the name of a file in the app settings search path, with or without `.json` |
| `-r`, `--run` | tool or workflow to run, also a workflow file by the name in it; repeat for several |
| `-w`, `--workflow` | workflow file to run: a path, or a file name in the workflow search path (see [Workflow files](/userguide/workflows.md#workflow-files)); repeat for several |
| `--dry-run` | validate the runs against the first rows of the files; run nothing |
| `--override GROUP.FIELD=VALUE` | set a setting for every step of every run, over the settings in the files; repeatable. `output.save=true` saves the results of every step. `output.formats=table:csv,plot:svg` saves tables as `.csv` and plots as `.svg` (or as JSON, for options such as `[{"kind": "plot", "format": "png", "dpi": 600}]`); kinds not named keep their formats. `processing.strict=false` uses the closest matching column for a column that is not in the data; `processing.strict.features=false` does so for one setting only. `processing.skippable.features=some` and `processing.required.features=FLIRR` as in a workflow file's `processing` section (see [Workflow files](/userguide/workflows.md#workflow-files)). The settings of the tools themselves (`config`) can't be set this way. The run summary lists the overrides, and `resolved.json` holds the overridden settings, so a rerun of it needs none. |
| `-e`, `--executor` | where and how the tasks run: `local` (default), `dask-local` or `dask`, with their options, for example `-e local:workers=4`. An unknown name is an error. |
| `--no-prefect-server` | don't start a local Prefect server if none is found; a temporary one is used instead (see [Prefect server](/install/index.md#prefect-server)). |
| `--log-dir` | log folder (`log` > `dir`); default: the output folder (see [Log files](/install/index.md#log-files)) |
| `--cache-dir` | sets the cache folder setting (`cache` > `dir`) |
| `-l`, `--log` | logging level: `debug`, `info` (default), `warning`, `error` or `critical`. The messages are shown in the terminal. |

These options can also be set with environment variables (see [Environment variables](/userguide/settings.md#environment-variables)). An option given on the command line takes precedence.

**Deprecated options.** These options still work, but print a warning that shows the new form:

| Deprecated | Use instead | Example | Removed in |
|---|---|---|---|
| `-c`, `--config FILE` | `-s`, `--settings FILE` | `-c settings.json` → `-s settings.json` | 0.8.0 |
| `--allow-guesses` | `--override processing.strict=false` | `--allow-guesses` → `--override processing.strict=false` | 0.8.0 |
| `-e LocalExecutor`, `LocalDaskExecutor`, `DaskExecutor` | `-e local`, `dask-local`, `dask` | `-e LocalDaskExecutor` → `-e dask-local` | 1.0.0 |
| `-a`, `--execargs` | the options after the executor name: `-e NAME:KEY=VALUE,...`; `num_workers` is now `workers` | `--execargs="num_workers=4"` → `-e local:workers=4` | 0.8.0 |

`DaskExecutor` without an address starts a Dask cluster on this computer, as `dask-local` does.

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
