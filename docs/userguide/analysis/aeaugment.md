# Autoencoder: Augment Data

The `Autoencoder: Augment Data` tool creates simulated copies of a table with models saved by [Autoencoder: Train](/userguide/analysis/aetrain). Each copy is the model's reconstruction of the data, by default after adding random noise. The tool can run on a GPU, see [Using a GPU](/install/index.md#using-a-gpu).

**Menu Access:** `Analysis` > `Autoencoder: Augment Data`

**Tool panel icon:** ![](/images/analysis/aeaugment.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front. The dialog's `Data` choice starts with this table; you can choose another one there (see [Choosing the data](/userguide/dialogs.md#choosing-the-data)).

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Autoencoder: Augment Data` menu.

3. In the `Configuration: Autoencoder: Augment Data` dialog, set:
    - `Copies`: the number of simulated copies of the table (default 1).
    - `Add noise` (checked by default): add random (white) noise to the features before the model reconstructs them. The noise is different on every run; there is no random seed.
    - `Signal-to-noise (dB)`: the ratio of signal to noise, in decibels (default 0). For each feature, the noise power is the mean signal power divided by 10^(dB/10): at 0 dB the noise is as strong as the signal, at 10 dB it has a tenth of its power.
    - `Model files`: the `.model` files saved by `Autoencoder: Train`. Use `Add...` to add files and `Remove` to remove the selected ones. Select at least one. Each model gives its own result.
    - `Grouping`: select at least one category column. The last one, e.g. `Cell`, is renumbered in each copy, so that the copies don't share cells. If its values are numbers, the first copy keeps them, and each further copy adds the largest number plus 1 once more. Otherwise, the copies append `.0`, `.1`, ... to the values.
    - `Features`: the same features the models were trained on. They are used in the order of the table's columns. `All features` uses all numeric columns of the table (see [Features](/userguide/dialogs.md#features)).
    - `Device` and `Threads`, in the `Resources` section: see [Resources](/userguide/dialogs.md#resources).

4. Click `OK`.

5. For each model file, the result is shown in a new table window, `Table: Simulated-<file>`. It has the category columns of the input and the simulated features, in the units of the input and sorted by name. It has one row per input row and copy; the input rows themselves are not included. For each signal with amplitude features (e.g. `FAD a1`, `FAD a2`), the relative amplitudes in percent (e.g. `FAD a1[%]`) are calculated again from the simulated amplitudes.
