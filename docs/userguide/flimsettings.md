# The flimsettings command

`flimsettings` lists, shows, validates, resolves and updates FLIMAnalyzer settings without the GUI: tool files, workflow files, app settings files, the user settings file and the environment variables. Use it to examine a file before you give it to `flimbatch` or to the GUI, or to find out which settings a session uses.

```
flimsettings OBJECT ACTION [OPTIONS]
```

`OBJECT` is `tool`, `workflow`, `app`, `user` or `env`. Each call does exactly one action, for example `--list` or `--show`. `flimsettings OBJECT --help` lists the actions of an object. With uv, run it as `uv run flimsettings ...`.

```
flimsettings tool --list
flimsettings workflow --show "Basic FLIRR Analysis"
flimsettings tool --validate summary.json
flimsettings app --show -s lab
flimsettings env --show
```

## Output and exit codes

* The result goes to standard output. Problems and warnings go to standard error, as `flimsettings: ...` and `flimsettings: warning: ...`.
* The exit code is 0 if the action is done and no problem is found. It is 1 if a validation finds a problem or the action can't be done, for example because a file doesn't exist. It is 2 if the arguments are not valid, for example no action or two actions.
* `flimsettings` doesn't start the GUI and doesn't load wxPython. It changes no file, except with `--update`.
* Of the environment variables, it shows only the `FLIM_*` variables, never others, for example those of Prefect.

## Files and names

The actions of `tool` and `workflow` take a `FILE`. A `FILE` is one of these, in this order:

1. A path, relative to the current folder or absolute.
2. A file name in the workflow search path, with or without `.json`. For example, `summary` finds `summary.json`. `-w DIR` sets the folders of the search path, as with `flimbatch`; else `FLIM_WORKFLOW_PATH` sets them, else the search path is the folder `workflows` in the platform's settings folder (see [Workflow files](/userguide/workflows.md#workflow-files)). `flimsettings` reads no settings file to find the search path.
3. A built-in workflow file, for example `import`.

`--show` also takes a `NAME`: the name of a tool (`tool --show`) or of a workflow defined in code (`workflow --show`). If no file has this name, `--show NAME` prints the default settings of the tool or workflow as a tool file. A file takes precedence over a tool or workflow of the same name.

A file must be of the kind of the object: a tool file for `tool`, a workflow file for `workflow`. A file of another kind is an error, and the message names the command for that kind of file:

```
$ flimsettings tool --show import
flimsettings: .../flim/workflow/files/import.json: a workflow file, not a tool file (flimsettings workflow --show import)
```

The name of a tool where a file is necessary is also an error:

```
$ flimsettings tool --validate Filter
flimsettings: 'Filter' is a tool, not a tool file; --validate takes a file; flimsettings tool --list lists the tool files
```

## tool

Tool files hold the settings of one tool, as a tool dialog's `Save Settings...` writes them (see [The settings of a tool](/userguide/settings.md#the-settings-of-a-tool)).

| Action | |
|---|---|
| `--list` | the tools by menu, the tools that are in no menu, the tool files in the workflow search path, and the workflow search path |
| `--show FILE\|NAME` | prints a tool file as it is, or a tool's default settings as a tool file |
| `--validate FILE` | validates a tool file as `flimbatch` validates it before a run |
| `--resolve FILE` | prints a tool file with every setting stated, as `flimbatch` runs it |
| `--update FILE` | rewrites a tool file of an older version in the current version |

`--list`, shortened (`/Users/mst3k` is the home folder):

```
$ flimsettings tool --list
Tools by menu (flimbatch --run NAME; quote names with spaces):
  File: Open Tables
  Data: Collect Files, Concatenate, Directory/File to Source, Drop Columns, Filter, ...
  Analysis: Autoencoder Augment Data, Autoencoder Run, Calculate, ...
  Plot: Bar Plot, Box Plot, FLIRR Plot, Frequency Histogram, ...

Not in the menus (by name or as a workflow step):
  Autoencoder Train Model

Tool files (flimbatch --run FILE, by path or file name):
  summary.json  (/Users/mst3k/Library/Application Support/FLIMAnalyzer/workflows)

Workflow search path:
  /Users/mst3k/Library/Application Support/FLIMAnalyzer/workflows
```

`--show NAME` prints the defaults of a tool. Save the output to a file to start a tool file:

```
$ flimsettings tool --show Summarize > summary.json
$ cat summary.json
{
  "schema_version": 2,
  "tool": "Summarize",
  "config": {
    "classname": "flim.tools.statistics.Summarize",
    "grouping": [],
    "features": [],
    "prefix": null,
    "resources": {
      "preferred_device": "cpu",
      "preferred_threads": 1
    },
    "aggs": ["count", "min", "max", "mean", "std", "sem", "median",
             "percentile(25)", "percentile(75)", "sum"],
    "single_table": true
  },
  "output": {
    "save": false,
    "formats": []
  }
}
```

`--validate FILE` validates the tool's settings. A valid file gives one line; a problem goes to standard error, with the exit code 1:

```
$ flimsettings tool --validate summary.json
/Users/mst3k/flim/summary.json: a valid tool file of Summarize

$ flimsettings tool --validate bad.json
flimsettings: /Users/mst3k/flim/bad.json:
  step 01 (Summarize): settings not valid: aggs.1: Input should be 'count', 'min', 'max', 'mean', 'std', 'sem', 'median', 'percentile(25)', 'percentile(75)' or 'sum'
```

`--validate` also gives warnings. For example, `"save": false` gives a warning, because `flimbatch` always saves the results of a tool run.

`--resolve FILE` prints the file with every setting stated, as `flimbatch` runs it: every field of the tool's settings, `output` with `save` and the format of each kind of result, and `processing`. The settings that depend on the data, for example `features: all` and the columns guessed with `"strict": false`, stay as in the file; `flimbatch` writes them into `resolved.json` (see [Batch Mode](/userguide/batch)). A file with problems is not resolved: the problems are shown, with the exit code 1.

`--override GROUP.FIELD=VALUE` (repeatable) shows the result of the same `--override` given to `flimbatch`, for example `processing.strict=false`. The tool's settings (`config`) can't be overridden. The end of the output:

```
$ flimsettings tool --resolve summary.json --override processing.strict=false
...
  "output": {
    "save": true,
    "formats": [
      {
        "kind": "table",
        "format": "tsv"
      }
    ]
  },
  "processing": {
    "strict": false,
    "skippable": {
      "grouping": "none",
      "features": "none"
    }
  }
}
```

`--update FILE` rewrites a tool file of an older version in the current version. The original file is kept next to it as `<name>.v<version>.json`, which the older FLIMAnalyzer version can still read. A file that has settings that can't be used, or that is already of the current version, is not changed; the exit code is then 1.

```
$ flimsettings tool --update old-summary.json
old-summary.json: updated to the current format; the original is kept as old-summary.v1.json
```

## workflow

Workflow files define a workflow as a list of steps (see [Workflow files](/userguide/workflows.md#workflow-files)). Workflows defined in code, such as `Basic FLIRR Analysis`, are part of FLIMAnalyzer.

| Action | |
|---|---|
| `--list` | the workflows defined in code, the workflow files, and the workflow search path |
| `--show FILE\|NAME` | prints a workflow file as it is, or the default settings of a workflow defined in code as a tool file |
| `--validate FILE` | validates a workflow file as `flimbatch` validates it before a run |
| `--resolve FILE` | prints a workflow file with every setting of every step stated, as `flimbatch` runs it |

`workflow` has no `--update`.

```
$ flimsettings workflow --list
Workflows defined in code (flimbatch --run NAME):
  Autoencoder Train  (built-in, Analysis)
  Basic FLIRR Analysis  (built-in, Workflow)
  FLIM Data Augmentation Tuning  (built-in, Workflow)
  FLIM Feature Analysis  (built-in, Workflow)
  Import Tables  (built-in, File)

Workflow files (flimbatch --run NAME, or by path or file name):
  Import  (built-in)
  FLIRR summary  (/Users/mst3k/Library/Application Support/FLIMAnalyzer/workflows/flirr-summary.json)

Workflow search path:
  /Users/mst3k/Library/Application Support/FLIMAnalyzer/workflows
```

The list shows each workflow file by the `name` in the file. `--show`, `--validate` and `--resolve` find a file by its file name, not by this `name`: `flimsettings workflow --show import` prints the built-in `Import` workflow file (`import.json`).

`--show NAME` with a workflow defined in code prints its default settings as a tool file. A tool file of a workflow defined in code runs that workflow with the file's settings (`flimbatch --run FILE`):

```
$ flimsettings workflow --show "Basic FLIRR Analysis"
{
  "schema_version": 2,
  "tool": "Basic FLIRR Analysis",
  "config": {
    "classname": "flim.workflow.basicflow.BasicFLIRR",
    "grouping": ["Treatment", "FOV", "Cell"],
    "features": ["FAD a1", "FAD a1%", "FAD a2", "FAD a2%", "FAD t1", "FAD t2",
                 "FAD photons", "NAD(P)H a1", "NAD(P)H a1%", "NAD(P)H a2",
                 "NAD(P)H a2%", "NAD(P)H t1", "NAD(P)H t2", "NAD(P)H photons"],
    "prefix": null,
    "resources": {
      "preferred_device": "cpu",
      "preferred_threads": 1
    },
    "reference_value": null,
    "fad_a1": null,
    "nadph_a2": null
  },
  "output": {
    "save": false,
    "formats": []
  }
}
```

This file is a tool file: validate, resolve and update it with `flimsettings tool`.

`--validate FILE` validates the structure of the workflow file and the settings of each step. It also finds the problems of saving, for example a workflow in which no step saves its results.

```
$ flimsettings workflow --validate flirr-summary
/Users/mst3k/Library/Application Support/FLIMAnalyzer/workflows/flirr-summary.json: a valid workflow file (FLIRR summary)
```

`--resolve FILE` prints the workflow file with every setting of every step stated: the step's `inputs`, every field of its tool's settings, its `output` and its `processing`. The workflow's own `output` and `processing` are applied to the steps. As with `tool --resolve`, the settings that depend on the data stay as in the file, and `--override GROUP.FIELD=VALUE` shows the result of the same `flimbatch --override`. The output, shortened to the second step:

```
$ flimsettings workflow --resolve flirr-summary --override output.formats=table:csv
{
  "schema_version": 1,
  "name": "FLIRR summary",
  ...
    {
      "id": "2",
      "tool": "Summarize",
      "inputs": ["1"],
      "description": "",
      "config": {
        "classname": "flim.tools.statistics.Summarize",
        "grouping": [],
        "features": ["FLIRR"],
        ...
        "aggs": ["count", "mean"],
        "single_table": true
      },
      "output": {
        "save": true,
        "formats": [{"kind": "table", "format": "csv"}]
      },
      "processing": {
        "strict": true,
        "skippable": {"grouping": "none", "features": "none"}
      }
    }
  ]
}
```

## app

App settings files hold the app settings and the settings of the tools for a session (see [App settings files](/userguide/settings.md#app-settings-files)).

| Action | |
|---|---|
| `--list` | the app settings files in the app settings search path, and the search path |
| `--show` | the app settings of `flimanalyzer` and of `flimbatch`, and where each value comes from |
| `--validate FILE` | validates an app settings file, as the GUI and `flimbatch` read it |
| `--update FILE` | rewrites an app settings file of an older version in the current version |

`--list` doesn't list tool and workflow files that are in the same folders; it gives their number.

```
$ flimsettings app --list
App settings files (-s NAME or -s FILE):
  lab  (/Users/mst3k/Library/Application Support/FLIMAnalyzer/appsettings)

App settings search path:
  /Users/mst3k/Library/Application Support/FLIMAnalyzer/appsettings
```

`--show` shows the app settings of the two commands: each value, where it comes from, and the command-line options and environment variables that change it. `-s FILE` adds an app settings file, as `-s` of `flimanalyzer` and `flimbatch` does (a path, or a name in the app settings search path). Without `-s`, the GUI's settings include the default app settings file, if you have set one. The command-line options of the two commands are not included. A setting with the same value and origin in the two commands has one line; else each command has its own line. For example (the values depend on your settings):

```
$ flimsettings app --show -s course
App settings of flimanalyzer and flimbatch, without command-line options.
Order of precedence, highest first: command line, environment, app settings file
(-s), user settings file (flimanalyzer only), built-in defaults.

App settings file of flimanalyzer: /Users/mst3k/Library/Application Support/FLIMAnalyzer/appsettings/course.json
App settings file of flimbatch: /Users/mst3k/Library/Application Support/FLIMAnalyzer/appsettings/course.json
User settings file (flimanalyzer only): /Users/mst3k/Library/Application Support/FLIMAnalyzer/usersettings.json

  Results folder:
      flimanalyzer: /Users/mst3k/results  (from app settings file)
      flimbatch:    not used: flimbatch saves under -o
      set with -o, FLIM_RESULTS_DIR
  Executor:
      dask-local, 4 workers, scheduler: threads  (from app settings file)
      set with -e, FLIM_EXECUTION__*
  Prefect server:
      yes (Prefect profile: local)  (from built-in default)
      set with --prefect-server, --no-prefect-server, FLIM_PREFECT_SERVER
  Server timeout:
      60 s  (from built-in default)
      set with --server-timeout, FLIM_SERVER_TIMEOUT
  Log folder:
      default (/Users/mst3k/Library/Logs/FLIMAnalyzer); logs kept 30 days  (from built-in default)
      set with --log-dir, FLIM_LOG_DIR
```

If a command can't use the file, its line says `refused, see above`, and the problems are on standard error.

`--validate FILE` takes the path of an app settings file. It shows the schema version of the file, the settings converted to the current version, and the problems (see [Settings files from older versions](/userguide/settings.md#settings-files-from-older-versions)). The exit code is 1 if the file can't be used, if it has invalid values or unknown settings, or if it has settings of tools that aren't installed, which `flimbatch` refuses. A tool file or a workflow file is not an app settings file: this is an error.

```
$ flimsettings app --validate lab.json
lab.json: schema version 1
Converted to the current version:
  working_dir to results_dir
  autosave and results_dir of 1 tool to its output section
```

`--update FILE` takes a path or a name in the app settings search path. It rewrites the file in the current version and keeps the original next to it as `<name>.v<version>.json`. As with `tool --update`, a file that has settings that can't be used, or that is already of the current version, is not changed, and the exit code is 1.

```
$ flimsettings app --update lab
/Users/mst3k/Library/Application Support/FLIMAnalyzer/appsettings/lab.json: updated to the current format; the original is kept as /Users/mst3k/Library/Application Support/FLIMAnalyzer/appsettings/lab.v1.json
```

## user

`flimsettings user --show` prints the path and the content of the user settings file (see [The user settings file](/userguide/settings.md#the-user-settings-file)). The file is only read: a file that the GUI can't read is not renamed. `FLIM_USER_SETTINGS` sets another path for the file. If there is no user settings file, the output says so:

```
$ flimsettings user --show
No user settings file: /Users/mst3k/Library/Application Support/FLIMAnalyzer/usersettings.json
```

## env

| Action | |
|---|---|
| `--list` | the `FLIM_*` variables that FLIMAnalyzer reads, what each sets and which commands read it, and the order of precedence |
| `--show` | the `FLIM_*` variables that are set, with unknown names and invalid values |

`--list`, shortened:

```
$ flimsettings env --list
Environment variables FLIMAnalyzer reads.
A command-line option takes precedence over its environment variable; an
environment variable takes precedence over the settings files and the built-in
defaults. Order of precedence of the app settings, highest first: command line,
environment, app settings file (-s), user settings file (flimanalyzer only),
built-in defaults.

  FLIM_APP_SETTINGS_PATH
      folders searched for app settings files, separated by ':'; read by flimanalyzer, flimbatch, flimsettings
  FLIM_CACHE_DIR
      cache folder (--cache-dir); read by flimanalyzer, flimbatch
  FLIM_DRY_RUN
      true: a dry run (--dry-run); read by flimbatch
  ...
  FLIM_WORKFLOW_PATH
      folders searched for workflow and tool files, separated by ':' (-w); read by flimanalyzer, flimbatch, flimsettings
```

`--show` prints the `FLIM_*` variables that are set. A name that FLIMAnalyzer doesn't read, for example a misspelled name, and a value that is not valid are problems: they go to standard error, and the exit code is 1.

```
$ export FLIM_LOG_LEVEL=loud FLIM_RESULT_DIR=/Users/mst3k/results
$ flimsettings env --show
FLIM_* environment variables that are set:
  FLIM_LOG_LEVEL=loud
  FLIM_RESULT_DIR=/Users/mst3k/results
flimsettings: problems:
  FLIM_RESULT_DIR: FLIMAnalyzer does not read this variable; check the name
  Invalid environment variable: FLIM_LOG_LEVEL=loud
```

## Example: from the defaults to a batch run

1. Get the default settings of a tool or of a workflow defined in code as a tool file:

   ```
   flimsettings workflow --show "Basic FLIRR Analysis" > flirr.json
   ```

2. Edit the file, for example `grouping` and `features` in `config`. The file has the defaults, also `"save": false` in `output`; `flimbatch` always saves the results of a tool and warns about this setting, unless you set it to `true` or run with `--override output.save=true`.
3. Validate the file:

   ```
   flimsettings tool --validate flirr.json
   ```

4. Look at every setting that the run will use:

   ```
   flimsettings tool --resolve flirr.json
   ```

5. Validate the run against the data, then run it (see [Batch Mode](/userguide/batch)):

   ```
   flimbatch -i data/ -o results/ --run flirr.json --dry-run
   flimbatch -i data/ -o results/ --run flirr.json
   ```
