# Autoencoder: Run

The `Autoencoder: Run` tool applies models saved by [Autoencoder: Train](/userguide/analysis/aetrain) to a table. For each row, it gives the encoded values and the reconstructed features. The tool can run on a GPU, see [Using a GPU](/install/index.md#using-a-gpu).

**Menu Access:** `Analysis` > `Autoencoder: Run`

**Tool panel icon:** ![](/images/analysis/aerun.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front. The dialog's `Data` choice starts with this table; you can choose another one there (see [Choosing the data](/userguide/dialogs.md#choosing-the-data)).

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Autoencoder: Run` menu.

3. In the `Configuration: Autoencoder: Run` dialog, set:
    - `Model files`: the `.model` files saved by `Autoencoder: Train`. Use `Add...` to add files and `Remove` to remove the selected ones. Select at least one. Each model gives its own results.
    - `Features`: the same features the models were trained on. They are used in the order of the table's columns. `All features` uses all numeric columns of the table (see [Features](/userguide/dialogs.md#features)).
    - `Device` and `Threads`, in the `Resources` section: see [Resources](/userguide/dialogs.md#resources).

4. Click `OK`.

5. For each model file, the results are shown in two new table windows, with the category columns of the input and one row per input row:
    - `Table: Reconstructed-<file>`: the reconstructed features, `Recon Feature 1`, `Recon Feature 2`, ..., in the order of the features. They are on the scale the model works with, from 0 to 1, not in the units of the input.
    - `Table: Features-<file>`: the encoded values, `Feature 1`, `Feature 2`, ...
