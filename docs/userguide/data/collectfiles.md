# Collect Files

The `Collect Files` tool lists the files that several earlier steps made, in one table: a row for each file, with the step input it came from. For example, the `Autoencoder Train` workflow uses it to list the model files of all its trainings (see [Autoencoder Train](/userguide/analysis/aetrain.md)).

**Menu Access:** none. Its inputs are files, and the GUI has no windows for files, so `Collect Files` is in no menu and not in the tool panel. Use it as a step of a workflow file (see [Workflow files](/userguide/workflows.md#workflow-files)) or in `flimbatch`.

## Settings

`Collect Files` has no settings of its own.

## Inputs

One input that takes several outputs of earlier steps (`files`), each a file or a list of files. In a workflow file, the step's `inputs` name these outputs. An output without files adds no rows.

## Result

`Table: Files`, with two columns:

- `Input`: the name of the input the file came from, for example the label of a training, `128-0.0001-1e-08`.
- `File`: the file's path.

The rows are in the order of the inputs, and within an input in the order of its files.

`flimsettings tool --show "Collect Files"` prints its tool file with the default settings, to start a workflow step from (see [The flimsettings command](/userguide/flimsettings)).
