# Directory/File to Source

The `Directory/File to Source` tool adds the `Source` column (each row's file as a URI, see [The Source column](load.md#the-source-column)) to a table imported with FLIMAnalyzer 0.6 or earlier, from its `Directory` and `File` columns. Tables are not converted automatically: a column named `File` may mean something else in your data.

**Menu Access:** `Data` > `Directory/File to Source`

**Tool panel icon:** ![](/images/data/source.png)

1. Select `Data` > `Directory/File to Source`.

2. In the dialog, set:

    - `Keep Directory and File` (checked by default): unchecked, the two columns are removed.
    - `Rename existing columns as` (default `{name} (before {tool})`): if the table already has a `Source` column, it is renamed, for example to `Source (before Add Source)` (`Add Source` is the tool's short name). The dialog warns about this and fills in `Renamed columns`, where you can change the new name.

3. Click `OK`.

The result is `Table: With Source`. Folders recorded on Windows (`D:\KCCI data\9SR`) and on macOS or Linux (`/data/9SR`) both work; spaces and other special characters are written percent-encoded (`file:///D:/KCCI%20data/9SR/Results-a.txt`).
