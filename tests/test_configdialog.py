"""The generic configuration dialog (flim.gui.configdialog) and its field editors."""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

wx = pytest.importorskip("wx")

import flim.tools  # noqa: E402,F401  (registers the tools)
from flim.configs import (  # noqa: E402
    CategorizerConfig,
    KMeansConfig,
    LinePlotConfig,
    RelativeChangeConfig,
    ScatterPlotConfig,
)
from flim.core.execution import ExecutionOptions  # noqa: E402
from flim.core.registry import tools  # noqa: E402

TOOLS = [t for group in tools.by_category().values() for t in group]


@pytest.fixture
def table():
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "Treatment": pd.Categorical(["Ctrl", "Drug"] * 10),
            "FOV": pd.Categorical(["1", "2"] * 10),
            "Cell": pd.Categorical([str(i) for i in range(20)]),
            "FLIRR": rng.random(20),
            "x": rng.random(20),
            "y": rng.random(20),
        }
    )


@pytest.fixture
def data_choices(table):
    return {"Table: data": table, "Table: other": table[["Treatment", "x"]]}


def marker(d, name):
    m = d.fields.markers[name]
    return m.IsShown(), m.GetToolTipText()


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.name)
def test_every_tool_dialog_builds(dialog, tool):
    d = dialog(tool.name)
    assert d.fields.editors  # something to edit
    d.validate()
    if d.ok_button.IsEnabled():
        assert isinstance(d.result().config, tool.config_class)


def test_edit_and_result(dialog):
    d = dialog("K-Means", KMeansConfig(features=["x"]))
    editors = d.fields.editors
    editors["n_clusters"].set(5)
    editors["features"].set(["x", "FLIRR"])
    editors["init"].set("random")
    editors["random_seed"].set(None)
    d.validate()
    assert d.ok_button.IsEnabled()
    result = d.result()
    config = result.config
    assert (config.n_clusters, config.init, config.random_seed) == (5, "random", None)
    assert config.features == ["FLIRR", "x"]  # in the table's column order
    assert result.input_names == ["Table: data"]
    assert result.inputs[0] is d.data_choices["Table: data"]


def test_grouping_order(dialog):
    d = dialog("Summarize")
    d.fields.editors["grouping"].set(["FOV", "Treatment"])
    assert d.result().config.grouping == ["FOV", "Treatment"]
    d.fields.editors["grouping"].set(["Treatment", "Cell", "FOV"])
    assert d.result().config.grouping == ["Treatment", "Cell", "FOV"]


def test_unused_fields_and_order(dialog):
    d = dialog("K-Means")
    assert "grouping" not in d.fields.editors  # K-Means does not group
    names = list(d.fields.editors)
    # the tool's own settings first, the general ones after
    assert names.index("n_clusters") < names.index("random_seed")
    assert names.index("tolerance") < names.index("random_seed")
    # the result prefix names the results: in the Output section
    assert "prefix" not in names and list(d.output_fields.editors) == ["prefix"]
    # the field's title labels its editor
    label = d.fields.widgets["n_clusters"][0]
    assert isinstance(label, wx.StaticText) and label.GetLabel() == "Clusters"


def test_reference_values_are_offered(dialog):
    d = dialog("Relative Change", RelativeChangeConfig(features=["x"]))
    reference = d.fields.editors["reference_value"]
    assert reference.control.GetItems() == ["Ctrl", "Drug"]
    d.fields.editors["reference_group"].control.SetValue("FOV")
    assert reference.control.GetItems() == ["1", "2"]


def test_invalid_text_marks_the_field(dialog):
    d = dialog("K-Means", KMeansConfig(features=["x"]))
    d.fields.editors["tolerance"].control.SetValue("tiny")
    d.validate()
    assert marker(d, "tolerance") == (True, "'tiny' is not a number")
    assert not d.ok_button.IsEnabled()
    d.fields.editors["tolerance"].control.SetValue("0.001")
    d.validate()
    assert not marker(d, "tolerance")[0]
    assert d.ok_button.IsEnabled()


def test_constraint_violations_mark_the_field(dialog):
    d = dialog("K-Means", KMeansConfig(features=["x"]))
    d.fields.editors["tolerance"].control.SetValue("-1")
    d.validate()
    shown, text = marker(d, "tolerance")
    assert shown and "greater than 0" in text


def test_issues_against_the_input(dialog):
    config = RelativeChangeConfig(features=["x"], reference_value="Placebo")
    d = dialog("Relative Change", config)
    shown, text = marker(d, "reference_value")
    assert shown and "not a value of 'Treatment'" in text
    assert not d.ok_button.IsEnabled()
    d.fields.editors["reference_value"].control.SetValue("Ctrl")
    d.validate()
    assert not marker(d, "reference_value")[0] and d.ok_button.IsEnabled()


def test_columns_follow_the_selected_input(dialog):
    d = dialog("Summarize")
    features = d.fields.editors["features"]
    assert features.items == ["FLIRR", "x", "y"]
    d.input_controls[0].SetStringSelection("Table: other")
    d._on_input(None)
    assert features.items == ["x"]
    grouping = d.fields.editors["grouping"]
    assert grouping.items == ["Treatment"]


def test_missing_features_are_not_listed(dialog):
    d = dialog("K-Means", KMeansConfig(features=["gone"]))
    features = d.fields.editors["features"]
    assert "gone" not in features.items  # only the input's features
    assert features.get() == [] and not features.note.IsShown()  # ignored


def test_mixed_and_optional_fields(dialog):
    d = dialog("Line Plot", LinePlotConfig(features=["x"]))
    errorbar = d.fields.editors["errorbar"]
    for text, value in (("sd", "sd"), ("68", 68), ("", None)):
        errorbar.control.SetValue(text)
        assert d.result().config.errorbar == value


def test_rules_table(dialog):
    d = dialog("Categorize Data", CategorizerConfig(features=["x"]))
    rules = d.fields.editors["rules"]
    assert rules.grid.GetNumberRows() == 3
    rules.grid.SetCellValue(0, 3, "-0.4")  # overlaps the next rule (-0.5..0.5)
    d.validate()
    shown, text = marker(d, "rules")
    assert shown and "overlap" in text
    rules.grid.SetCellValue(0, 3, "-0.5")
    rules.grid.SetCellValue(0, 1, "x")
    rules.grid.SetCellValue(1, 1, "x")
    rules.grid.SetCellValue(2, 1, "x")
    d.validate()
    assert d.ok_button.IsEnabled()
    assert [r.feature for r in d.result().config.rules] == ["x", "x", "x"]


def test_nested_resources_section(dialog):
    d = dialog("Autoencoder: Train")
    resources = d.fields.editors["resources"]
    resources.fields.editors["preferred_device"].set("cpu")
    resources.fields.editors["preferred_threads"].set(2)
    d.fields.editors["features"].set(["x", "y"])
    d.fields.editors["grouping"].set(["FOV"])
    d.fields.editors["timeseries"].set("Treatment")
    d.validate()
    config = d.result().config
    assert (config.resources.preferred_device, config.resources.preferred_threads) == (
        "cpu",
        2,
    )
    # tools whose resources allow only one value have no resources section
    assert "resources" not in dialog("Sort").fields.editors


def test_model_files(dialog, tmp_path):
    d = dialog("Autoencoder: Run")
    d.fields.editors["model_files"].set([tmp_path / "a.model"])
    d.fields.editors["features"].set(["x"])
    d.validate()
    assert d.result().config.model_files == [tmp_path / "a.model"]


def test_inputs_of_tools_with_several(dialog, table):
    merge = dialog("Merge")
    assert merge.selected_names() == ["Table: data", "Table: other"]
    concat = dialog("Concatenate")
    assert concat.selected_names() == [["Table: data", "Table: other"]]
    assert set(concat.result().inputs[0]) == {"Table: data", "Table: other"}
    # choices shown by their labels, stored by their values
    direction = concat.fields.editors["mode"]
    assert direction.control.GetStrings() == [
        "Rows (stack below)",
        "Columns (side by side)",
    ]
    direction.control.SetSelection(1)
    assert concat.result().config.mode == "horizontal"


def test_execution_options(dialog, tmp_path):
    d = dialog(
        "Sort", execution=ExecutionOptions(execution={"executor": "local", "workers": 3})
    )
    d.autosave.SetValue(True)
    d.validate()
    assert not d.ok_button.IsEnabled()
    assert "Choose the folder" in d.status.GetLabel()
    d.folder.SetPath(str(tmp_path))
    d.validate()
    execution = d.result().execution
    assert execution.autosave.enabled and execution.autosave.results_dir == Path(tmp_path)
    assert execution.execution.workers == 3  # other options are kept


def test_results_folder_that_cannot_be_used(dialog, tmp_path):
    (tmp_path / "file").write_text("x")
    d = dialog("Sort")
    d.autosave.SetValue(True)
    d.folder.SetPath(str(tmp_path / "file" / "results"))
    d.validate()
    assert not d.ok_button.IsEnabled()
    assert "is not a folder" in d.status.GetLabel()


@pytest.mark.skipif(os.name == "nt", reason="symbolic links need extra rights")
def test_results_folder_is_stored_canonical(dialog, tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    d = dialog("Sort")
    d.autosave.SetValue(True)
    d.folder.SetPath(str(tmp_path / "link"))
    d.validate()
    assert d.result().execution.autosave.results_dir == Path(tmp_path / "real")


def test_autosave_locked(dialog, tmp_path):
    options = ExecutionOptions()
    d = dialog("Sort", execution=options, autosave_locked=True)
    assert d.autosave.GetValue() and not d.autosave.IsEnabled()


def test_registered_dialog_and_open(wxapp, table, monkeypatch):
    from flim.gui import configdialog

    class SortDialog(configdialog.ConfigDialog):
        pass

    from flim.configs import SortConfig

    before = configdialog._DIALOGS.get(SortConfig)  # Sort's own registration
    configdialog.register_dialog(SortConfig)(SortDialog)
    try:
        assert configdialog.dialog_class(SortConfig) is SortDialog
        assert configdialog.dialog_class(KMeansConfig) is configdialog.ConfigDialog
        monkeypatch.setattr(SortDialog, "ShowModal", lambda self: wx.ID_OK)
        result = configdialog.open_config_dialog(
            None,
            tools.get("Sort"),
            SortConfig(features=["x"]),
            data_choices={"t": table},
        )
        assert result.config.features == ["x"]
        monkeypatch.setattr(SortDialog, "ShowModal", lambda self: wx.ID_CANCEL)
        assert (
            configdialog.open_config_dialog(
                None, tools.get("Sort"), data_choices={"t": table}
            )
            is None
        )
    finally:
        if before is None:
            configdialog._DIALOGS.pop(SortConfig)
        else:
            configdialog._DIALOGS[SortConfig] = before


def test_registered_field_editor(dialog):
    from flim.gui import editors

    class Upper(editors.TextEditor):
        def get(self):
            return super().get().upper()

    editors.register_editor(KMeansConfig, "cluster_prefix")(Upper)
    try:
        d = dialog("K-Means", KMeansConfig(features=["x"]))
        assert isinstance(d.fields.editors["cluster_prefix"], Upper)
        assert d.result().config.cluster_prefix == "CLUSTER"
    finally:
        editors._FIELD_EDITORS.pop((KMeansConfig, "cluster_prefix"))


def test_all_features_checks_every_feature(dialog):
    d = dialog("Box Plot")
    features = d.fields.editors["features"]
    features.set(["x"])
    features.all.SetValue(True)
    features._on_all(wx.CommandEvent())
    assert features.checked() == features.items == ["FLIRR", "x", "y"]
    assert not features.list.IsEnabled() and not features.buttons[0].IsEnabled()
    assert d.result().config.features == "all"
    # unchecked again: the selection made before
    features.all.SetValue(False)
    features._on_all(wx.CommandEvent())
    assert features.checked() == ["x"] and features.list.IsEnabled()
    assert d.result().config.features == ["x"]


def test_all_features_from_a_config_and_new_inputs(dialog):
    from flim.configs import BoxPlotConfig

    d = dialog("Box Plot", BoxPlotConfig(features="all"))
    features = d.fields.editors["features"]
    assert features.checked() == ["FLIRR", "x", "y"]
    assert not features.list.IsEnabled()
    assert d.result().config.features == "all"
    d.input_controls[0].SetStringSelection("Table: other")
    d._on_input(None)
    assert features.checked() == ["x"]  # all features of the other table
    features.all.SetValue(False)
    features._on_all(wx.CommandEvent())  # no selection before: all stay checked
    assert features.checked() == ["x"]


def test_nested_settings_are_inline_and_advanced_ones_collapsed(dialog):
    config = ScatterPlotConfig(points={"mode": "all", "samples": 5000})
    d = dialog("Scatter Plot", config)
    points = d.fields.editors["points"]
    assert not isinstance(points.control, wx.CollapsiblePane)  # no extra click
    editors = points.fields.editors
    assert editors["mode"].get() == "all" and editors["samples"].get() == 5000
    editors["mode"].set("sample")
    points.fields.refresh()
    assert editors["samples"].control.IsShown()
    editors["samples"].set(20000)
    result = d.result().config.points
    assert (result.mode, result.samples) == ("sample", 20000)
    training = dialog("Autoencoder: Train")
    assert isinstance(training.fields.editors["resources"].control, wx.CollapsiblePane)


def test_missing_features_are_guessed(dialog):
    d = dialog("K-Means", KMeansConfig(features=["X", "gone"]))  # the input has "x"
    features = d.fields.editors["features"]
    assert features.get() == ["x"]
    assert features.note.GetLabel() == "Guessed: X → x"  # 'gone': ignored


def test_tall_dialog_fits_a_small_screen(dialog, monkeypatch):
    # a laptop screen: 768 px, of which 718 are usable (taskbar or menu bar)
    class SmallDisplay:
        GetFromWindow = staticmethod(lambda window: 0)

        def __init__(self, index=0):
            pass

        def GetClientArea(self):
            return wx.Rect(0, 0, 1366, 718)

    monkeypatch.setattr(wx, "Display", SmallDisplay)
    import flim.workflow  # noqa: F401  (registers the workflows)

    d = dialog("FLIM Feature Analysis")
    assert d.GetSize().height <= 718
    assert d.ok_button.GetRect().GetBottom() <= d.GetClientSize().height
    assert d.fields.GetBestSize().height > d.scroll.GetSize().height  # it scrolls


def test_split_needs_a_column_to_split_by(dialog):
    from flim.configs import SplitConfig

    d = dialog("Split")
    d.validate()
    assert marker(d, "grouping") == (True, "Select at least 1 grouping column")
    assert not d.ok_button.IsEnabled()
    d = dialog("Split", SplitConfig(grouping=["Treatment"]))
    d.validate()
    assert not marker(d, "grouping")[0] and d.ok_button.IsEnabled()


def test_save_formats_of_the_tool_outputs(dialog, tmp_path):
    from flim.core.saving import PlotSaveOptions, TableSaveOptions

    kmeans = dialog("K-Means")
    assert kmeans.save_kinds() == ["table"]  # its only declared output
    assert list(kmeans.formats.editors) == ["table_formats"]
    # outputs known only when it runs: all kinds
    d = dialog("Box Plot")
    assert d.save_kinds() == ["table", "plot"]
    d.autosave.SetValue(True)
    d.folder.SetPath(str(tmp_path))
    d.formats.editors["plot_formats"].set(["png", "svg"])
    d.formats.editors["plot_dpi"].set(150)
    d.validate()
    formats = d.result().execution.autosave.formats
    assert formats == [
        TableSaveOptions(), PlotSaveOptions(dpi=150), PlotSaveOptions(format="svg")
    ]


def test_a_kind_without_format_is_an_error(dialog, tmp_path):
    d = dialog("Box Plot")
    d.autosave.SetValue(True)
    d.folder.SetPath(str(tmp_path))
    d.formats.editors["plot_formats"].set([])
    d.validate()
    assert d.formats.markers["plot_formats"].IsShown()
    assert any("at least one format" in i.message for i in d.execution_issues())
    d.autosave.SetValue(False)  # not saving: the formats don't matter
    d.validate()
    assert not d.formats.markers["plot_formats"].IsShown()


@pytest.mark.parametrize("stored, follows", [(None, True), ("default", True), ("other", False)])
def test_use_the_default_folder(dialog, tmp_path, stored, follows):
    default, other = tmp_path / "default", tmp_path / "other"
    folder = {None: None, "default": default, "other": other}[stored]
    execution = ExecutionOptions(autosave={"enabled": folder is not None, "results_dir": folder})
    d = dialog("K-Means", execution=execution, default_folder=default)
    assert d.use_default.GetValue() is follows
    assert d.folder.IsEnabled() is not follows
    d.autosave.SetValue(True)
    d.validate()
    if follows:  # settings from before that stored the default folder: follow it too
        assert d.folder.GetPath() == str(default)
        assert d._autosave(stored=True).results_dir is None
        assert d._autosave().results_dir == default  # where the run saves
    else:
        assert d._autosave(stored=True).results_dir == other


def test_a_folder_inside_the_default_folder_is_kept_relative(dialog, tmp_path):
    from pathlib import Path

    default = tmp_path / "default"
    inside, outside = default / "kmeans", tmp_path / "other"
    execution = ExecutionOptions(autosave={"enabled": True, "results_dir": inside})
    d = dialog("K-Means", execution=execution, default_folder=default)
    assert not d.use_default.GetValue()
    assert d._autosave(stored=True).results_dir == Path("kmeans")  # moves with the default
    assert d._autosave().results_dir == inside  # where this run saves
    assert "kept as kmeans" in d.folder_note.GetLabel()
    d.folder.SetPath(str(outside))
    d._on_folder()
    assert d._autosave(stored=True).results_dir == outside
    assert d.folder_note.GetLabel() == "Outside the default folder, kept as this path."
    d.folder.SetPath(str(default))  # the default folder itself: none stored
    d._on_folder()
    assert d._autosave(stored=True).results_dir is None
    # a relative folder from the settings is shown inside the default folder
    assert d._shown_folder(Path("kmeans")) == str(inside)


def test_without_a_results_folder_set_folders_are_kept_as_full_paths(dialog, tmp_path):
    # the default is then only the start folder, which can change between sessions
    default = tmp_path / "start"
    inside = default / "kmeans"
    execution = ExecutionOptions(autosave={"enabled": True, "results_dir": inside})
    d = dialog("K-Means", execution=execution, default_folder=default, keep_relative=False)
    assert d._autosave(stored=True).results_dir == inside
    assert d.folder_note.GetLabel().startswith("Kept as this path")


def test_no_default_folder_controls_without_a_default(dialog):
    d = dialog("K-Means")
    assert d.use_default is None and d.make_default is None



def test_dialog_sections(dialog, tmp_path):
    d = dialog("K-Means")
    boxes = [
        c.GetSizer().GetStaticBox().GetLabel()
        for c in d.GetSizer().GetChildren()
        if c.IsSizer() and isinstance(c.GetSizer(), wx.StaticBoxSizer)
    ]
    assert boxes == ["Input", "Settings", "Output"]
    # the prefix is read and checked like the other fields
    d.output_fields.editors["prefix"].set("run1")
    d.fields.editors["features"].set(["x"])
    d.validate()
    assert d.result().config.prefix == "run1"


def test_no_input_section_without_data(dialog):
    d = dialog("K-Means", data_choices={})
    boxes = [
        c.GetSizer().GetStaticBox().GetLabel()
        for c in d.GetSizer().GetChildren()
        if c.IsSizer() and isinstance(c.GetSizer(), wx.StaticBoxSizer)
    ]
    assert boxes == ["Settings", "Output"]


@pytest.mark.parametrize("tool", ["Series Analysis", "Random Forest", "Heatmap"])
def test_grouping_is_hidden_where_it_has_no_effect(dialog, tool):
    assert "grouping" not in dialog(tool).fields.editors


def test_pca_random_seed_is_hidden(dialog):
    assert "random_seed" not in dialog("PCA").fields.editors
    assert "random_seed" in dialog("K-Means").fields.editors  # used there


def test_dialog_shows_the_example_and_the_data_checks(dialog):
    from flim.configs import FuseCategoriesConfig

    d = dialog("Fuse Categories", FuseCategoriesConfig(grouping=["Treatment", "FOV"]))
    assert d.example.IsShown()
    assert d.example.GetLabel().startswith("Example: Treatment ")
    assert "→ Treatment:FOV " in d.example.GetLabel()
    d.fields.editors["delimiter"].set("r")  # occurs in "Drug"
    issues = d.validate()
    assert any(i.field == "delimiter" and i.severity == "warning" for i in issues)
    assert d.ok_button.IsEnabled()  # a warning: the tool can still run


def test_no_example_line_for_other_tools(dialog):
    assert not dialog("K-Means").example.IsShown()


def test_save_results_and_the_two_folders(dialog, tmp_path):
    """`Use the default folder` switches the field between the default folder and
    the tool's own one; without `Save results` the controls below are greyed."""
    default, own = tmp_path / "default", tmp_path / "own"
    execution = ExecutionOptions(autosave={"enabled": True, "results_dir": own})
    d = dialog("K-Means", execution=execution, default_folder=default)
    assert d.autosave.GetLabel() == "Save results"
    assert not d.use_default.GetValue() and d.folder.GetPath() == str(own)
    assert d.folder.IsEnabled() and d.make_default.IsEnabled()
    d.use_default.SetValue(True)
    d._on_use_default()
    assert d.folder.GetPath() == str(default) and not d.folder.IsEnabled()
    assert not d.make_default.IsEnabled()
    d.use_default.SetValue(False)
    d._on_use_default()
    assert d.folder.GetPath() == str(own) and d.folder.IsEnabled()  # the own folder again
    # not saving: everything below is greyed and keeps its values
    d.autosave.SetValue(False)
    d.validate()
    assert not any(c.IsEnabled() for c in (d.folder, d.use_default, d.make_default))
    assert not any(panel.IsEnabled() for panel in d.formats.panels)
    assert d.folder.GetPath() == str(own)
    d.autosave.SetValue(True)
    d.validate()
    assert d.folder.IsEnabled() and d.use_default.IsEnabled()


def test_own_folder_starts_with_the_default(dialog, tmp_path):
    default = tmp_path / "default"
    d = dialog("K-Means", default_folder=default)
    assert d.use_default.GetValue()
    d.use_default.SetValue(False)
    d._on_use_default()
    assert d.folder.GetPath() == str(default)  # no folder of its own yet
    assert not d.make_default.IsEnabled()  # it is the default already


def test_read_settings_fields(wxapp):
    """Tabs are shown as \\t and kept (a stripped tab read tab-separated files as one
    column); lists of words are one line separated by commas."""
    from flim.configs import ImportTablesConfig
    from flim.core.fields import describe
    from flim.gui.editors import editor_for

    frame = wx.Frame(None)
    try:
        specs = {s.name: s for s in describe(ImportTablesConfig)}
        assert specs["extensions"].title == "Files to include"
        editors = {n: editor_for(ImportTablesConfig, specs[n])(frame, specs[n]) for n in specs}
        defaults = ImportTablesConfig()
        for name in ("delimiter", "extensions", "exclude"):
            editors[name].set(getattr(defaults, name))
        assert editors["delimiter"].control.GetValue() == "\\t,"
        assert editors["delimiter"].get() == "\t,"
        assert editors["extensions"].control.GetValue() == ".txt, .csv"
        editors["extensions"].control.SetValue("txt, CSV, .dat")
        config = ImportTablesConfig(extensions=editors["extensions"].get())
        assert config.extensions == [".txt", ".csv", ".dat"]
        editors["exclude"].control.SetValue("")
        assert editors["exclude"].get() == []
    finally:
        frame.Destroy()


def test_import_tables_dialog_keeps_the_tab(dialog):
    from flim.configs import ImportTablesConfig

    d = dialog("Import Tables", data_choices={})
    config, issues = d.current_config()
    assert config.delimiter == "\t," and config == ImportTablesConfig()


def test_separate_names_keep_empty_entries(wxapp):
    from flim.configs.data import SeparateCategoriesConfig
    from flim.core.fields import describe
    from flim.gui.editors import editor_for

    frame = wx.Frame(None)
    try:
        spec = next(s for s in describe(SeparateCategoriesConfig) if s.name == "names")
        editor = editor_for(SeparateCategoriesConfig, spec)(frame, spec)
        editor.control.SetValue(", Treatment, Cell")
        assert editor.get() == ["", "Treatment", "Cell"]  # the empty name skips a part
    finally:
        frame.Destroy()


def test_separate_delimiters_as_characters(wxapp):
    from flim.configs.data import SeparateCategoriesConfig
    from flim.core.fields import describe
    from flim.gui.editors import editor_for

    frame = wx.Frame(None)
    try:
        spec = next(s for s in describe(SeparateCategoriesConfig) if s.name == "delimiters")
        editor = editor_for(SeparateCategoriesConfig, spec)(frame, spec)
        editor.set(["-", "_", "\t"])
        assert editor.control.GetValue() == "-_\\t"
        editor.control.SetValue(":, ")  # a comma and a space are delimiters too
        assert editor.get() == [":", ",", " "]
        editor.set(["::", "-"])  # longer delimiters: as a list
        assert editor.control.GetValue() == '["::", "-"]' and editor.get() == ["::", "-"]
    finally:
        frame.Destroy()
