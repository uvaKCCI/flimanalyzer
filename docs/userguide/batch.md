# Batch Mode

`flimbatch` reads data files and runs tools or workflows on them without opening the GUI, for example on a computing cluster or from a script. A [workflow file](/userguide/workflows.md#workflow-files) says exactly what a run does with the files. A tool runs with its settings from a tool file, which `Save Settings...` in the tool's dialog writes.

```
flimbatch -i data/ -o results/ --run Import
flimbatch -i data/ -o results/ --run my-analysis.json
flimbatch -i data/ -o results/ --run Import --run summarize.json
```

With uv, run it as `uv run flimbatch ...`. `flimanalyzer --batch ...` does the same as `flimbatch ...`, but is deprecated and is removed in 0.8.0. On Windows, use `flimbatch`. There, `flimanalyzer` starts without a console window, so its messages are not shown.

## Steps

1. **Settings:** `flimbatch` reads the app settings file given with `-s`: a path, or the name of a file in the app settings search path (see [App settings files](/userguide/settings.md#app-settings-files)). `-s` takes only app settings files; a tool file given with `-s` is refused, and the message says to give it to `--run`. The file can be from this or an older FLIMAnalyzer version. `flimbatch` uses the file only if every setting in it can be used and validated: it stops with an error if the file can't be read, comes from a newer version, or has invalid values, unknown settings or settings of tools that aren't installed (see [Settings files from older versions](/userguide/settings.md#settings-files-from-older-versions)). Without `-s`, the built-in defaults are used. Environment variables and the other command-line options take precedence over the file (see [Where the settings come from](/userguide/settings.md#where-the-settings-come-from)). `flimbatch` does not read the user settings file, so its results don't depend on settings changed in the GUI, and it writes no settings file, so a run never changes what the GUI starts with.
2. **Reading:** for each `--run`, it reads each file given with `-i` into a table of its own, with the columns `Source` (the file as a URI), `Directory` and `File` added (see [The Source column](/userguide/data/load.md#the-source-column)). Folders are searched with their subfolders for the files with the extensions of `Files to include` in the read settings (default: `.txt` and `.csv`). `-x` leaves out files by their names, for example `-x Results-a-ctrl-1.txt`. Nothing else is done to the data: renaming, dropping and calculating columns, categories from the file names and joining the files into one table are steps of a workflow, for example of the built-in `Import` workflow. The files are read with the settings of the `Open Tables` tool in the settings file (see [Read settings](/userguide/data/load.md#read-settings)); without them, tab and comma separate columns. `--run "Import Tables"` reads them with the settings of `Import Tables` in the settings file instead, and runs the workflow they name (`workflow`). By default, they name no workflow: then `--run "Import Tables"` stops with an error. As for every tool given by its name, taking these settings from the app settings file is deprecated (see [Deprecated options](#deprecated-options)): save them as a tool file of `Import Tables` (`Save Settings...` in its dialog, or `flimsettings workflow --show "Import Tables"` and edit `workflow`), and run it with `--run FILE`. It reads the files with the file's read settings and runs the workflow the file names. A file that can't be read is skipped with a warning.
3. **Tools and workflows:** it runs each `--run` on the tables, in the order given. See [Tools and workflows](#tools-and-workflows).

`flimbatch` needs at least one `--run`. To read the files into one table, run the built-in `Import` workflow: `--run Import`. It also renames the channels' columns and drops the other channels' columns, and it calculates the FLIM features (see [Import Tables](/userguide/data/load.md#import-tables)).

## Tools and workflows

`--run` takes one of these:

* A name: of a tool, for example `Summarize`, of a workflow defined in code, for example `Basic FLIRR Analysis`, or of a workflow file in the workflow search path, by the `name` in the file.
* A file: a workflow file or a tool file, given as a path, or as a file name ending in `.json` in the workflow search path or, after it, among the built-in workflow files, for example `import.json` (see [Where workflow files are found](/userguide/workflows.md#where-workflow-files-are-found)). An argument that contains a folder separator or ends with `.json` is a file.

They run as follows:

* A workflow file runs as its steps say: each step once per table, until a step such as `Concatenate` joins the tables into one (see [Workflow files](/userguide/workflows.md#workflow-files)). A workflow file in which no step saves is refused (see [Saving](/userguide/workflows.md#saving)).
* A tool runs as a workflow of one step, `01`: once on each table, or, for a tool that takes several tables such as `Concatenate`, once on all of them. A tool file runs the same way, with the tool's settings, formats and `processing` from the file.
* A workflow defined in code, such as `Basic FLIRR Analysis`, runs once on each table. A tool file of a workflow defined in code runs that workflow with the settings of the file.

A tool or a workflow defined in code that is given by its name runs with its default settings. With `-s`, it takes its settings from the `tools` section of the app settings file instead; if the file has no settings of the tool, `flimbatch` stops with an error. Taking a tool's settings from the app settings file is deprecated (see [Deprecated options](#deprecated-options)): give the settings as a tool file. To start a tool file, `flimsettings tool --show NAME` prints the default settings of a tool as a tool file, and `flimsettings workflow --show NAME` those of a workflow defined in code (see [flimsettings](/userguide/flimsettings)). Change the settings in the file and run it with `--run FILE`.

Most tools need features selected in their settings (at least one, some two; see [Tool dialogs](/userguide/dialogs.md)), and for most tools the defaults select none: without them, `flimbatch` stops with an error that names the step, the tool and what is missing, for example `step 1 (Summarize): features: 0 entries apply (none); Summarize needs at least 1`.

`flimbatch` always saves the results of a tool. `"save": false` in a tool's settings applies in the GUI only, and the tool's results folder (`output.results_dir`) is replaced by `-o`. `flimbatch` prints a warning for each of these settings that it doesn't use.

Tools that need two tables, such as `Merge`, can't run with `--run` alone; use them in a workflow file. The workflow `FLIM Feature Analysis` uses each table both as training data and as the data to analyze.

## Results

Each call of `flimbatch` saves its results in a folder of its own, named after the date and time it started: `<output>/<date and time>/`, where `<output>` is the folder given with `-o`. For example `results/2026-11-03_14-05-31/`. If another call started in the same second, `-2`, `-3` and so on is added to the name. The folder holds:

* A folder per `--run`, `run-1`, `run-2` and so on, numbered in the order of the `--run` options. Each one holds:
    * `run_summary.txt`: when the run started and ended, how long it took (`Elapsed`), its state, the settings files used, the overrides, notes, warnings and the versions of FLIMAnalyzer and its libraries (see [The run summary](/userguide/workflows.md#the-run-summary)).
    * `resolved.json`: the run's settings with every setting stated, as a workflow file (for a workflow defined in code, as a tool file). It states every setting of every step, the formats of each kind of result, and the columns the run used where the settings leave them to the data (`features: all`, guessed columns, skipped entries). Run it with `--run resolved.json` on the same files to repeat the run, also with a later FLIMAnalyzer version whose defaults changed. `flimsettings workflow --resolve FILE` and `flimsettings tool --resolve FILE` show a file with every setting stated before a run.
    * A folder per step that saves its results, `<id>-<tool>`, for example `01-Summarize` or `04-Calculate`. Below it, the results of a step that runs once per table are in a folder per table, and the results of a step that makes its results in parts (for example a table per feature) are in a folder per part. A workflow defined in code saves the results of each table in a folder named after the table.
* `flimbatch.log`: the log of the call. If a log folder is set (`--log-dir`, `FLIM_LOG_DIR` or `log` > `dir` in the app settings file), the log is in that folder instead, in a file named after the call's start and its process ID, for example `flimbatch_2026-11-03T14-05-31_12345.log` (see [Log files](/install/index.md#log-files)).

For example, the results of `flimbatch -i data/ -o results/ --run Import --run summarize.json`, where `summarize.json` is a tool file of `Summarize` that makes a table per feature:

```
results/
  2026-11-03_14-05-31/
    flimbatch.log
    run-1/
      run_summary.txt
      resolved.json
      04-Calculate/
        Table_Calculated.txt
    run-2/
      run_summary.txt
      resolved.json
      01-Summarize/
        a.txt/
          FLIRR/
            Table_Summary_FLIRR.txt
          ...
```

The formats of the results are described in [Formats](/userguide/workflows.md#formats). For a tool, they are the formats of the tool's `output` section, or, for each kind it doesn't list, tables as tab-separated `.txt` files and plots as `.png` files at 300 dpi.

When it finishes, `flimbatch` returns the exit code 0 if every run completed without failed tasks, and 1 if a validation or a task failed. Invalid options give the exit code 2. Scripts can test this code to see whether the run worked.

## Validating a run first

With `--dry-run` (or the environment variable `FLIM_DRY_RUN=true`), `flimbatch` runs nothing. It validates:

* the output folder given with `-o`: that it can be reached and written to. `-o` is also needed with `--dry-run`. The log of the dry run is written into this folder, or into the log folder if one is set, in a file named after the start and the process ID, for example `flimbatch_2026-11-03T14-05-31_12345.log`.
* the executor: that its packages are installed and, for `dask`, that the Dask cluster answers within the server timeout.
* the Prefect server (see [Prefect server](/install/index.md#prefect-server)).
* every run, against the first 20 rows of each file: the settings of the tools and, for a workflow file, every step against the columns it gets, and the rules of [Saving](/userguide/workflows.md#saving).

It reports what it found. The first and the last line of the output say that it is a dry run, and whether `--dry-run` or `FLIM_DRY_RUN` made it one. The exit code is 0 if the validation found no error, else 1.

## Missing columns

Before a workflow runs, its settings are validated against the data (see [Workflows](/userguide/workflows)). A workflow may need a column that the data doesn't have, for example `FAD a1%` when the data has `FAD a1[%]`. This is an error, unless the tool file or the workflow file allows guesses or skipped entries in its `processing` section: `"processing": {"strict": false}` uses the closest matching column, and the run summary lists it under "Notes" (see `processing` under [Workflow files](/userguide/workflows.md#workflow-files)). `--override processing.strict=false` does the same for every step of every run.

## Options

```{tabularcolumns} \Y{0.32}\Y{0.68}
```

| Option | |
|---|---|
| `-i`, `--input` | data files or folders (required). Takes several values, and can be repeated: `-i a.txt -i b.txt` is the same as `-i a.txt b.txt`. On macOS and Linux, the shell expands wildcards, for example `-i data/*.txt`; on Windows, give a folder instead. |
| `-x`, `--exclude` | files not to read, by their exact file name (no folder, no wildcards). Takes several values, and can be repeated: `-x a.txt -x b.txt`. |
| `-o`, `--output` | folder for the results (required, also with `--dry-run`). `flimbatch` stops with a message if it can't be reached or written to. |
| `-s`, `--settings` | app settings file: a path, or the name of a file in the app settings search path, with or without `.json` |
| `-r`, `--run` | tool or workflow to run: a name, or a workflow file or a tool file (see [Tools and workflows](#tools-and-workflows)). Repeat it for several runs; they run in the order given. |
| `-w`, `--workflow-path` | folders searched for workflow files and tool files. They replace the folders of `FLIM_WORKFLOW_PATH` and the default folder (see [Where workflow files are found](/userguide/workflows.md#where-workflow-files-are-found)). Takes several values, and can be repeated. |
| `-e`, `--executor` | where and how the tasks run: `local` (default), `dask-local` or `dask`, with their options, for example `-e local:workers=4`. An unknown name is an error. |
| `--prefect-server`, `--no-prefect-server` | `--prefect-server` uses a local Prefect server, and starts one if none is found. `--no-prefect-server` uses a temporary Prefect server for each run instead (see [Prefect server](/install/index.md#prefect-server)). |
| `--server-timeout SECONDS` | how long to wait for responses of the Prefect server, and of the Dask cluster if one is used (default: 60). Below 60, a local Prefect server that is started may not be ready in time. |
| `--log-dir` | log folder (`log` > `dir`); default: the call's results folder (see [Results](#results) and [Log files](/install/index.md#log-files)) |
| `-l`, `--log-level` | logging level: `debug`, `info` (default), `warning`, `error` or `critical`; also `--log`. The messages are shown in the terminal. |
| `--dry-run` | validate the output folder, the executor, the Prefect server and the runs, against the first rows of the files; run nothing (see [Validating a run first](#validating-a-run-first)) |
| `--override GROUP.FIELD=VALUE` | set a setting for every step of every run, over the settings in the files; repeatable. `output.save=true` saves the results of every step. A workflow defined in code always saves its results: `output.save=false` for its run is an error; limit it to the other runs with a prefix (see below). `output.formats=table:csv,plot:svg` saves tables as `.csv` and plots as `.svg` (or as JSON, for options such as `[{"kind": "plot", "format": "png", "dpi": 600}]`); kinds not named keep their formats. `processing.strict=false` uses the closest matching column for a column that is not in the data; `processing.strict.features=false` does so for one setting only. `processing.skippable.features=some` and `processing.required.features=FLIRR` as in a workflow file's `processing` section; a step whose `features` has no entries, for example a Concatenate step, is not affected (see [Workflow files](/userguide/workflows.md#workflow-files)). The settings of the tools themselves (`config`) can't be set this way. A prefix limits an override to one run or one step: `run-2.output.save=true` applies to the second `--run` only, and `run-2.steps.3.output.save=false` to step 3 of the second `--run` (with a single `--run`, `steps.3.output.save=false` is enough). The more specific override takes precedence: one for a step over one for a run, over one for every run, over the settings in the files. The run summary lists the overrides, and `resolved.json` holds the overridden settings, so a rerun of it needs none. |

`-e`, `--prefect-server`, `--server-timeout`, `--log-dir`, `-l` and `--dry-run` can also be set with environment variables: `FLIM_EXECUTION` (or `FLIM_EXECUTION__EXECUTOR` and the other `FLIM_EXECUTION__` variables), `FLIM_PREFECT_SERVER`, `FLIM_SERVER_TIMEOUT`, `FLIM_LOG_DIR`, `FLIM_LOG_LEVEL` and `FLIM_DRY_RUN`, and `-w` with `FLIM_WORKFLOW_PATH` (see [Environment variables](/userguide/settings.md#environment-variables)). The other options have no environment variable. An option given on the command line takes precedence.

### Deprecated options

These options and forms still work, but print a warning that shows the new form:

```{tabularcolumns} >{\raggedright\arraybackslash}\Y{0.24}>{\raggedright\arraybackslash}\Y{0.28}>{\raggedright\arraybackslash}\Y{0.36}>{\raggedright\arraybackslash}\Y{0.12}
```

| Deprecated | Use instead | Example | Removed in |
|---|---|---|---|
| `-c`, `--config FILE` | `-s`, `--settings FILE` | `-c settings.json` → `-s settings.json` | 0.8.0 |
| `--allow-guesses` | `--override processing.strict=false` | `--allow-guesses` → `--override processing.strict=false` | 0.8.0 |
| `-e LocalExecutor`, `LocalDaskExecutor`, `DaskExecutor` | `-e local`, `dask-local`, `dask` | `-e LocalDaskExecutor` → `-e dask-local` | 1.0.0 |
| `-a`, `--execargs` | the options after the executor name: `-e NAME:KEY=VALUE,...`; `num_workers` is now `workers` | `--execargs="num_workers=4"` → `-e local:workers=4` | 0.8.0 |
| `--run NAME` with the tool's settings from the `-s` file | `--run FILE` with a tool file | `-s settings.json --run Summarize` → `--run summarize.json` | 0.8.0 |

`DaskExecutor` without an address starts a Dask cluster on this computer, as `dask-local` does.

The options of the GUI (`flimanalyzer`) are listed in [Command-line options](/install/index.md#command-line-options). The executors and their arguments, and how to run `flimbatch` on an HPC cluster with Slurm, are described in [Concurrent and Distributed Execution](/userguide/execution).

## Running in Docker

The Docker images run `flimbatch` (see [Installing with Docker](/install/index.md#installing-with-docker) for the images). Use `-v` to make the folder with the data and the tool or workflow files available inside the container as `/work`:

```
docker run --rm -v "$PWD:/work" ghcr.io/uvakcci/flimanalyzer:latest-cpu \
    -i data/ -o results/ --run summarize.json --no-prefect-server
```

- On Linux, add `-u $(id -u)` so that the result files belong to you, not to the image's user.
- With the CUDA image, add `--gpus all` to use the GPU.
- With `--no-prefect-server`, each run uses a temporary Prefect server. To report to a Prefect server instead, give its address with the `docker run` option `-e`, before the image name. For example: `-e PREFECT_API_URL=http://prefect.example.org:4200/api`.
