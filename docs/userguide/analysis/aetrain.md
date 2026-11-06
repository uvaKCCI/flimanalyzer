# Autoencoder: Train

The `Autoencoder: Train` tool trains autoencoder models on selected features and saves them to files. An autoencoder is a neural network that compresses (encodes) the features of each data point into a few values and then reconstructs (decodes) the features from them. [Autoencoder: Run](/userguide/analysis/aerun) and [Autoencoder: Augment Data](/userguide/analysis/aeaugment) use the saved models. The tool can run on a GPU, see [Using a GPU](/install/index.md#using-a-gpu).

**Menu Access:** `Analysis` > `Autoencoder: Train`

**Tool panel icon:** ![](/images/analysis/aetrain.png)

## Running the Analysis

1. Go to the `Window` menu and select one of the data tables. This brings the selected table window to the front. The dialog's `Data` choice starts with this table; you can choose another one there (see [Choosing the data](/userguide/dialogs.md#choosing-the-data)).

2. Start the tool by clicking on its icon in the tool panel or via the `Analysis` > `Autoencoder: Train` menu.

3. In the `Configuration: Autoencoder: Train` dialog, set:
    - `Epochs`: the number of training passes through the data (default 20).
    - `Learning rates`, `Weight decays`, `Batch sizes`: one or more values each, separated by commas (defaults 0.0001, 1e-08 and 128). One model is trained for each combination of a learning rate, a weight decay and a batch size. For example, 2 learning rates and 2 batch sizes train 4 models.
    - `Time series`: a category column that is not used to split the data into training and validation sets (default `Treatment`); see `Grouping` below.
    - `Model name`: the start of the names of the saved model files (default `AEModel`).
    - `Rescale` (unchecked by default): show the reconstructed features in the units of the input. If unchecked, they are on the scale the model works with, from 0 to 1.
    - `Loss plots` (checked by default): a plot of the loss of each model.
    - `Training fraction`: the fraction of the groups used for training, more than 0 and less than 1 (default 0.7). The other groups are used for validation.
    - `Checkpoint every`: save the model every n epochs, and after the last epoch (default 20).
    - `Random seed`: with a number, every run uses the same split into training and validation sets and the same starting weights. Leave it empty (default) for a random split and random starting weights.
    - `Architecture`: the design of the network. The dialog shows the description and the layers of the selected architecture for the number of selected features.
    - `Grouping`: the data is split into training and validation sets by these groups (default `FOV`, `Cell`), so that all rows of a cell are in the same set. The `Time series` column is left out of this grouping. Without grouping, the rows are split at random.
    - `Features`: the features to train on. The default is the amplitudes, lifetimes and photon counts of FAD and NAD(P)H (`FAD a1` to `NAD(P)H photons`). This dialog has no `All features` option. [Autoencoder: Run](/userguide/analysis/aerun) and [Autoencoder: Augment Data](/userguide/analysis/aeaugment) need the same features.
    - `Device` and `Threads`, in the `Resources` section: see [Resources](/userguide/dialogs.md#resources).

    Before training, each feature is scaled to the range 0 to 1, with the minimum and maximum of the training set. Missing values are replaced by 0. The model file includes this scaling, so the other autoencoder tools apply it too.

    ![](/images/analysis/aetrain-config.png)

4. Check `Save results in` and choose a folder (see [Saving results](/userguide/dialogs.md#saving-results)). The model files are saved in its subfolder `Autoencoder_Train`. If `Save results in` is unchecked, they are saved in a temporary folder, and only a warning in the log names it.

5. Click `OK`.

6. Each model is labeled with its batch size, learning rate and weight decay, e.g. `128-0.0001-1e-08`. The results of each model are:
    - `Table: AE Loss-<label>`: for each epoch, the `Training Loss` and the `Validation Loss` (the mean squared error between the input and its reconstruction), and the `Model File` saved after that epoch (`---` if none).
    - `Plot: AE Loss-<label> Plot` (if `Loss plots` is checked): the training and validation loss of each epoch.
    - `Table: AE Decoded-<label>`: the reconstructed features of the last epoch, named `AE Recon <feature>`, with the category columns and a category column `Autoencoder` that tells whether the row was in the `training` or the `validation` set.
    - `Table: AE Encoded-<label>`: the encoded values of the last epoch, `AE Encoded 0`, `AE Encoded 1`, ..., with the same category columns.

    The rows of the decoded and encoded tables are not in the order of the input.

    The model files are named `<Model name>_<batch size>_<learning rate>_<weight decay>_epoch<NNNN>.model`, e.g. `AEModel_128_0.0001_1e-08_epoch0020.model`.
