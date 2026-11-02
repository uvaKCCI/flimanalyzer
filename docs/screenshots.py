"""Regenerates the screenshots of the user guide (docs/images), on macOS.

    uv run python docs/screenshots.py DATAFILE [NAME ...]

DATAFILE is a FLIM results table (tab-separated) with the columns Cell, FOV and
Treatment; the user guide uses 9SR-Mito-MASTER-ChiFilter.txt. Its Directory and File
columns are not shown. NAMEs (image paths below docs/images, e.g.
analysis/gmm-config.png) select screenshots; default: all.

Dialogs and windows are captured by their window number (``screencapture -l``: only
their own content, never other windows; the terminal needs the Screen Recording
permission), plots are saved directly. Windows open on the screen while it runs.
"""

import os
import subprocess
import sys

import matplotlib
import matplotlib.figure

matplotlib.use("Agg")

import pandas as pd  # noqa: E402
import wx  # noqa: E402

import flim.gui  # noqa: E402,F401  (registers the dialogs)
import flim.tools  # noqa: E402,F401  (registers the tools)
import flim.workflow  # noqa: E402,F401
from flim.configs import (  # noqa: E402
    ConcatConfig,
    FLIRRPlotConfig,
    GMMConfig,
    HistogramConfig,
    MergeConfig,
    PairPlotConfig,
    SortConfig,
    SplitConfig,
    SummaryConfig,
)
from flim.configs.analysis import (  # noqa: E402
    CategorizerConfig,
    CategoryRule,
    KMeansConfig,
    KSStatsConfig,
    PCAConfig,
    RandomForestConfig,
    RelativeChangeConfig,
    SeriesAnalysisConfig,
)
from flim.configs.plot import (  # noqa: E402
    BarPlotConfig,
    BoxPlotConfig,
    HeatmapConfig,
    HistogramRange,
    KDEConfig,
    LinePlotConfig,
    PointSampling,
    ScatterPlotConfig,
    SwarmPlotConfig,
    ViolinPlotConfig,
)
from flim.core.registry import tools  # noqa: E402

IMAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
DATAFILE = "9SR-Mito-MASTER-ChiFilter.txt"
TREATMENTS = ["ctrl", "Dox15", "Dox30", "Dox45", "Dox60"]
CATEGORIES = ["Treatment", "FOV", "Cell"]
DELAY = 800  # ms for a window to be drawn before it is captured


def load(path) -> pd.DataFrame:
    data = pd.read_csv(path, sep="\t")
    data = data.drop(columns=["Directory", "File"], errors="ignore")
    data["Treatment"] = pd.Categorical(data["Treatment"], categories=TREATMENTS)
    for column in ("FOV", "Cell"):
        data[column] = data[column].astype(str).astype("category")
    return data[CATEGORIES + [c for c in data.columns if c not in CATEGORIES]]


# --- tables shown in the examples, made from the data ---


def fov(value):
    """The rows of one field of view (the Concatenate example's two files)."""
    return lambda data: data[data["FOV"] == value].reset_index(drop=True)


def fad_a1_means(data):
    """The Merge example's second table: the mean FAD a1 of each cell."""
    config = SummaryConfig(grouping=CATEGORIES, features=["FAD a1"], aggs=["mean"])
    (table,) = tools.get("Summarize")()(data, config=config).values()
    return table


def result_of(tool, config, inputs="data", result=None):
    """A table made by a tool, e.g. the K-Means clusters for a scatter plot."""

    def make(data):
        table = data if inputs == "data" else inputs(data)
        results = tools.get(tool)()(table, config=config)
        return next(v for k, v in results.items() if result is None or k.endswith(result))

    return make


def pivoted(data):
    """What the data window's Pivot button makes of the Pivot example's choices."""
    columns = ["FAD a1[%]", "NAD(P)H a2[%]"]
    table = pd.pivot_table(
        data[columns + CATEGORIES],
        index=["FOV", "Cell"],
        columns=["Treatment"],
        observed=False,
    )
    table.columns = ["\n".join(col).strip() for col in table.columns.values]
    return table.reset_index()


# --- the screenshots: image path -> (kind, arguments) ---
# kinds: "main" (the application window), "dialog" (a tool's configuration dialog),
# "table" (a data window), "window" (another dialog of the application, made by a
# function of the shooter), "plot" (a figure of a tool's results)
#
# tables: "data", a function of the data, or a tool's result (tool, config, result)

GMM = GMMConfig(features=["FAD a1[%]", "NAD(P)H a2[%]"], n_components=3)
PAIRPLOT = PairPlotConfig(
    grouping=["Treatment"],
    x_vars=["FAD a1[%]", "NAD(P)H a2[%]", "FLIRR"],
    points=PointSampling(mode="sample", samples=5000),
)
# FAD a1[%]: near the top of the features table, so that it shows checked
HISTOGRAMS = [
    HistogramConfig(
        grouping=["Treatment"],
        histtype=style,
        table=True,
        features={"FAD a1[%]": HistogramRange(min=50, max=90, bins=40)},
    )
    for style in ("bar", "barstacked", "step", "stepfilled")
]
HISTOGRAM = HISTOGRAMS[0]  # the bar style, as the user guide's example
FLIRR = FLIRRPlotConfig(grouping=["Treatment", "FOV"])
SORT = SortConfig(features=["FAD a1"])

# Analysis
SUMMARY = SummaryConfig(
    features=["FAD a1[%]", "FLIRR"], aggs=["count", "mean", "std", "sem", "median"]
)
SUMMARY_GROUPED = SUMMARY.model_copy(update={"grouping": ["Treatment", "FOV"]})
KS = KSStatsConfig(features=["FAD a1"], comparison="Treatment")
KMEANS = KMeansConfig(features=["FAD a1", "NAD(P)H a1"], n_clusters=3)
FEATURES = ["FAD a1[%]", "FAD t1", "FAD t2", "NAD(P)H a2[%]", "NAD(P)H t1", "NAD(P)H t2", "FLIRR"]
PCA = PCAConfig(features=FEATURES, keep_original=True, explained_plot=True)
FOREST = RandomForestConfig(features=FEATURES, target="Treatment")
RELCHANGE = RelativeChangeConfig(
    grouping=["Treatment", "FOV"],
    features=["FAD a1[%]", "NAD(P)H a2[%]", "FLIRR"],
    reference_value="ctrl",
)
SERIES_COLUMNS = [f"FAD a1[%]\n{t}" for t in TREATMENTS]
SERIES = SeriesAnalysisConfig(features=SERIES_COLUMNS)
CATEGORIZE = CategorizerConfig(
    features=["FLIRR"],
    name="FLIRR level",
    rules=[
        CategoryRule(value="low", feature="FLIRR", min=0, max=0.25),
        CategoryRule(value="medium", feature="FLIRR", min=0.25, max=0.35),
        CategoryRule(value="high", feature="FLIRR", min=0.35, max=1),
    ],
)

# Plots: grouped by Treatment and FOV (result1), or FOV and Treatment (result2)
def grouped(config_class, feature="FLIRR", **options):
    return (
        config_class(grouping=["Treatment", "FOV"], features=[feature], **options),
        config_class(grouping=["FOV", "Treatment"], features=[feature], **options),
    )


BAR = grouped(BarPlotConfig)
BOX = grouped(BoxPlotConfig)
LINE = grouped(LinePlotConfig)
VIOLIN = grouped(ViolinPlotConfig)
SWARM = grouped(SwarmPlotConfig, "FLIRR\nmean")  # of the cell means
KDE = KDEConfig(grouping=["Treatment", "FOV"], features=["FLIRR"])
SCATTER = ScatterPlotConfig(grouping=["Treatment"], features=["FAD a1[%]", "NAD(P)H a2[%]"])
HEATMAP = HeatmapConfig(features=FEATURES, annotate=True)
CELL_MEANS = SummaryConfig(grouping=CATEGORIES, features=["FLIRR"], aggs=["mean"])
RELATIVE = RELCHANGE.model_copy(update={"features": ["FLIRR"]})
FLIRR_WORKFLOW = dict(
    grouping=["Treatment", "FOV"], features=["FAD a1[%]", "NAD(P)H a2[%]", "FLIRR"]
)

SPLIT = SplitConfig(grouping=["FOV"])
MERGE = MergeConfig(how="left", on=CATEGORIES)
TWO_FILES = {"example1.txt": fov("a"), "example2.txt": fov("b")}
MERGE_INPUTS = {DATAFILE: "data", "Table: Summary": fad_a1_means}

SHOTS = {
    "toolbar.png": ("main", {}),
    "data/exdata_table.png": ("table", {}),
    "data/dataframe.png": ("table", {}),
    # Data
    "data/precision.png": ("table", {"crop": (860, 28, 1000, 64)}),
    "files/open-dlg.png": ("window", {"make": "open_dialog"}),
    "files/import-dlg.png": ("window", {"make": "import_dialog"}),
    "data/category-filter.png": ("window", {"make": "category_filter"}),
    "data/filter-settings.png": ("window", {"make": "filter_settings"}),
    "data/sort-preresult.png": ("table", {}),
    "data/sort-config.png": ("dialog", {"tool": "Sort", "config": SORT}),
    "data/sort-results.png": ("table", {"tool": "Sort", "config": SORT}),
    "data/order-config.png": ("dialog", {"tool": "Order Categories", "setup": "show_treatment_order"}),
    "data/concat-config1.png": ("dialog", {"tool": "Concatenate", "config": ConcatConfig(), "inputs": TWO_FILES, "selected": [list(TWO_FILES)]}),
    "data/split-input.png": ("dialog", {"tool": "Split", "config": SPLIT}),
    "data/split-result.png": ("table", {"tool": "Split", "config": SPLIT, "result": "FOV=a"}),
    "data/merge-start.png": ("table", {}),
    "data/merge-summary.png": ("table", {"table": fad_a1_means, "title": "Table: Summary"}),
    "data/merge-dialog.png": ("dialog", {"tool": "Merge", "config": MERGE, "inputs": MERGE_INPUTS, "selected": list(MERGE_INPUTS)}),
    "data/merge-res1.png": ("table", {"tool": "Merge", "config": MERGE, "inputs": MERGE_INPUTS}),
    "data/merge-res3.png": ("table", {"tool": "Merge", "config": MERGE, "inputs": MERGE_INPUTS, "scroll_to_end": True}),
    "data/pivot-original.png": ("table", {}),
    "data/pivot-input.png": ("window", {"make": "pivot_groups"}),
    "data/pivot-columns.png": ("window", {"make": "pivot_columns"}),
    "data/pivot-result.png": ("table", {"table": pivoted, "title": DATAFILE}),
    # Analysis
    "analysis/summary-config-nogrouping.png": ("dialog", {"tool": "Summarize", "config": SUMMARY}),
    "analysis/summary-result1-nogrouping.png": ("table", {"tool": "Summarize", "config": SUMMARY, "size": (1000, 300)}),
    "analysis/summary-result1-grouping.png": ("table", {"tool": "Summarize", "config": SUMMARY_GROUPED}),
    "analysis/ks-config1.png": ("dialog", {"tool": "KS-Statistics", "config": KS}),
    "analysis/ks-results.png": ("table", {"tool": "KS-Statistics", "config": KS, "size": (1000, 400)}),
    "analysis/kmeans-config.png": ("dialog", {"tool": "K-Means", "config": KMEANS}),
    "analysis/kmeans-results1.png": ("table", {"tool": "K-Means", "config": KMEANS}),
    "analysis/kmeans-results2.png": ("plot", {"tool": "Scatter Plot", "config": ScatterPlotConfig(grouping=["Cluster"], features=["FAD a1", "NAD(P)H a1"]), "inputs": result_of("K-Means", KMEANS)}),
    "analysis/rf-start.png": ("table", {}),
    "analysis/pca-dialog.png": ("dialog", {"tool": "PCA", "config": PCA}),
    "analysis/pca-res.png": ("table", {"tool": "PCA", "config": PCA, "result": "Components"}),
    "analysis/pca-hist.png": ("plot", {"tool": "PCA", "config": PCA}),
    "analysis/rf-config.png": ("dialog", {"tool": "Random Forest", "config": FOREST}),
    "analysis/rf-output.png": ("plot", {"tool": "Random Forest", "config": FOREST}),
    "analysis/rf-output2.png": ("table", {"tool": "Random Forest", "config": FOREST, "size": (700, 400)}),
    "analysis/relchange-config-grouping.png": ("dialog", {"tool": "Relative Change", "config": RELCHANGE}),
    "analysis/relchange-result-grouping.png": ("table", {"tool": "Relative Change", "config": RELCHANGE}),
    "analysis/relpivot-result.png": ("table", {"table": pivoted}),
    "analysis/seriesanalysis-config.png": ("dialog", {"tool": "Series Analysis", "config": SERIES, "inputs": {"Table: pivoted": pivoted}}),
    "analysis/seriesanalysis-results.png": ("table", {"tool": "Series Analysis", "config": SERIES, "inputs": pivoted}),
    "analysis/categorize-config.png": ("dialog", {"tool": "Categorize Data", "config": CATEGORIZE}),
    "analysis/categorize-results.png": ("table", {"tool": "Categorize Data", "config": CATEGORIZE}),
    "analysis/gmm-config.png": ("dialog", {"tool": "Gaussian Mixed Model", "config": GMM}),
    "analysis/gmm-results1.png": ("table", {"tool": "Gaussian Mixed Model", "config": GMM, "result": "Feature Clustering"}),
    "analysis/gmm-results2.png": ("table", {"tool": "Gaussian Mixed Model", "config": GMM, "result": "Component Information Criteria", "size": (640, 260)}),
    # Plots
    "analysis/histogram-config.png": ("dialog", {"tool": "Frequency Histogram", "config": HISTOGRAM}),
    "analysis/histogram-results1.png": ("plot", {"tool": "Frequency Histogram", "config": HISTOGRAMS[0]}),
    "analysis/histogram-results2.png": ("plot", {"tool": "Frequency Histogram", "config": HISTOGRAMS[1]}),
    "analysis/histogram-results3.png": ("plot", {"tool": "Frequency Histogram", "config": HISTOGRAMS[2]}),
    "analysis/histogram-results4.png": ("plot", {"tool": "Frequency Histogram", "config": HISTOGRAMS[3]}),
    "analysis/histogram-results1a.png": ("table", {"tool": "Frequency Histogram", "config": HISTOGRAMS[0]}),
    "analysis/barplot-config-grouping.png": ("dialog", {"tool": "Bar Plot", "config": BAR[0]}),
    "analysis/barplot-result1-grouping.png": ("plot", {"tool": "Bar Plot", "config": BAR[0]}),
    "analysis/barplot-result2-grouping.png": ("plot", {"tool": "Bar Plot", "config": BAR[1]}),
    "analysis/boxplot-config-grouping.png": ("dialog", {"tool": "Box Plot", "config": BOX[0]}),
    "analysis/boxplot-result1-grouping.png": ("plot", {"tool": "Box Plot", "config": BOX[0]}),
    "analysis/boxplot-result2-grouping.png": ("plot", {"tool": "Box Plot", "config": BOX[1]}),
    "analysis/lineplot-config-grouping.png": ("dialog", {"tool": "Line Plot", "config": LINE[0]}),
    "analysis/lineplot-result1-grouping.png": ("plot", {"tool": "Line Plot", "config": LINE[0]}),
    "analysis/lineplot-result2-grouping.png": ("plot", {"tool": "Line Plot", "config": grouped(LinePlotConfig, "rel FLIRR")[1], "inputs": result_of("Relative Change", RELATIVE)}),
    "analysis/violinplot-config-grouping.png": ("dialog", {"tool": "Violin Plot", "config": VIOLIN[0]}),
    "analysis/violinplot-result1-grouping.png": ("plot", {"tool": "Violin Plot", "config": VIOLIN[0]}),
    "analysis/violinplot-result2-grouping.png": ("plot", {"tool": "Violin Plot", "config": VIOLIN[1]}),
    "analysis/dataframe-summary-grouped.png": ("table", {"table": result_of("Summarize", CELL_MEANS), "title": "Table: Summary"}),
    "analysis/swarmplot-config-grouping.png": ("dialog", {"tool": "Swarm Plot", "config": SWARM[0], "inputs": {"Table: Summary": result_of("Summarize", CELL_MEANS)}}),
    "analysis/swarmplot-result1-grouping.png": ("plot", {"tool": "Swarm Plot", "config": SWARM[0], "inputs": result_of("Summarize", CELL_MEANS)}),
    "analysis/swarmplot-result2-grouping.png": ("plot", {"tool": "Swarm Plot", "config": SWARM[1], "inputs": result_of("Summarize", CELL_MEANS)}),
    "analysis/scatter-config1.png": ("dialog", {"tool": "Scatter Plot", "config": SCATTER}),
    "analysis/scatter-results.png": ("plot", {"tool": "Scatter Plot", "config": SCATTER}),
    "analysis/heatmap-config.png": ("dialog", {"tool": "Heatmap", "config": HEATMAP}),
    "analysis/heatmap-results1.png": ("plot", {"tool": "Heatmap", "config": HEATMAP}),
    "analysis/heatmap-results2.png": ("table", {"tool": "Heatmap", "config": HEATMAP, "size": (1000, 400)}),
    "analysis/kde-config.png": ("dialog", {"tool": "KDE", "config": KDE}),
    "analysis/kde-results.png": ("plot", {"tool": "KDE", "config": KDE}),
    # Workflows: the graph of a run (of one field of view: the same steps, faster)
    "analysis/workflow-results.png": ("graph", {"tool": "Basic FLIRR Analysis", "config": FLIRR_WORKFLOW, "rows": fov("a")}),
    "analysis/flirr_data.png": ("table", {}),
    "analysis/flirr-config.png": ("dialog", {"tool": "FLIRR Plot", "config": FLIRR}),
    "analysis/flirr-result.png": ("plot", {"tool": "FLIRR Plot", "config": FLIRR}),
    "analysis/pairplot-config.png": ("dialog", {"tool": "Pair Plot", "config": PAIRPLOT}),
    "analysis/pairplot-results.png": ("plot", {"tool": "Pair Plot", "config": PAIRPLOT}),
}


def _objc():
    import ctypes
    import ctypes.util

    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    return objc


def _message(obj, selector, restype, *args):
    """An Objective-C message: [obj selector:args]."""
    import ctypes

    objc = _objc()
    send = objc.objc_msgSend
    send.restype = restype
    send.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [type(a) for a in args]
    return send(obj, objc.sel_registerName(selector), *args)


def _window_number(window) -> int:
    """The macOS window number (CGWindowID) of a wx window."""
    import ctypes

    nswindow = _message(window.GetHandle(), b"window", ctypes.c_void_p)
    return _message(nswindow, b"windowNumber", ctypes.c_long)


def _make_key(window) -> None:
    """Makes the window the one with the keyboard focus (drawn active)."""
    import ctypes

    nswindow = _message(window.GetHandle(), b"window", ctypes.c_void_p)
    _message(nswindow, b"makeKeyAndOrderFront:", None, ctypes.c_void_p(None))


def _activate() -> None:
    """Brings the application to the front, so that its windows are drawn active."""
    import ctypes

    app = _message(_objc().objc_getClass(b"NSApplication"), b"sharedApplication", ctypes.c_void_p)
    _message(app, b"activateIgnoringOtherApps:", None, ctypes.c_bool(True))


def capture(window, path, crop=None) -> None:
    """Saves the window (with its title bar) as a PNG. Captured by its window number:
    only the window's own content, also where other windows cover it. ``crop``: the
    part to keep (left, top, right, bottom, in points of the window)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(
        ["screencapture", "-x", "-o", f"-l{_window_number(window)}", path], check=True
    )
    # screencapture hides the extension in Finder and adds screen metadata: not wanted
    subprocess.run(["xattr", "-c", path], check=True)
    if crop is not None:
        from PIL import Image

        with Image.open(path) as image:
            scale = image.width / window.GetSize().width  # 2 on Retina displays
            box = tuple(round(v * scale) for v in crop)
            image.crop(box).save(path)


class Shooter:
    def __init__(self, data, names):
        from flim.core.tools import FLIMAnalyzer
        from flim.gui.app import AppFrame

        self.data = data
        self.names = list(names)
        self.results = {}
        self.frame = AppFrame(FLIMAnalyzer())
        self.frame.SetTitle("FLIMAnalyzer")  # not the version of a development build
        self.frame.Show()
        self.window = None

    # --- steps ---

    def next(self):
        if self.window is not None:
            self.window.Destroy()
            self.window = None
        if not self.names:
            self.frame.Destroy()
            return
        name = self.names.pop(0)
        kind, args = SHOTS[name]
        path = os.path.join(IMAGES, name)
        print(name)
        try:
            getattr(self, f"_{kind}")(path, **args)
        except Exception as err:  # report and go on with the next one
            print(f"  failed: {err!r}")
            wx.CallAfter(self.next)

    def _later(self, window, path, crop=None):
        self.window = window
        _activate()
        window.Raise()

        def shoot():
            _activate()
            _make_key(window)
            wx.CallLater(200, lambda: (capture(window, path, crop), self.next()))

        wx.CallLater(DELAY, shoot)

    def _main(self, path):
        self.frame.Raise()
        wx.CallLater(DELAY, lambda: (capture(self.frame, path), self.next()))

    def _dialog(self, path, tool, config=None, inputs=None, selected=None, setup=None):
        from flim.gui.configdialog import dialog_class

        tool = tools.get(tool)
        choices = self.tables(inputs or {"Table: data": "data"})
        dialog = dialog_class(tool.config_class)(
            self.frame, tool, config, data_choices=choices, selected=selected
        )
        if setup:
            getattr(self, setup)(dialog)
        dialog.Show()
        self._later(dialog, path)

    def _table(
        self,
        path,
        table="data",
        title=DATAFILE,
        tool=None,
        config=None,
        inputs=None,
        result=None,
        size=(1000, 560),
        scroll_to_end=False,
        crop=None,
    ):
        from flim.gui.datapanel import PandasFrame

        if tool is not None:
            results = self.run(tool, config, inputs)
            title = next(
                k
                for k, v in results.items()
                if isinstance(v, pd.DataFrame) and (result is None or k.endswith(result))
            )
            table = results[title]
        else:
            table = self.table(table)
        # the rows a window shows: sizing the columns to all rows of a large table
        # takes minutes
        window = PandasFrame(self.frame, title, data=table.head(500))
        window.SetSize(size)
        window.grid.AutoSizeColumns(setAsMin=False)  # headers not cut off
        if scroll_to_end:
            window.grid.MakeCellVisible(0, window.grid.GetNumberCols() - 1)
        window.Show()
        self._later(window, path, crop)

    def _window(self, path, make):
        window = getattr(self, make)()
        window.Show()
        self._later(window, path)

    def _plot(self, path, tool, config, inputs=None):
        results = self.run(tool, config, inputs)
        figure = next(
            v for v in results.values() if isinstance(v, matplotlib.figure.Figure)
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        figure.savefig(path, dpi=100, bbox_inches="tight")
        wx.CallAfter(self.next)

    def _graph(self, path, tool, config, rows=None):
        """The graph of a workflow run, as the application shows it after the run."""
        import tempfile

        from flim.core.graph import WorkflowGraph
        from flim.core.prefect_server import use_prefect_server

        workflow = tools.get(tool)
        data = self.table(rows or "data")
        with tempfile.TemporaryDirectory() as results, use_prefect_server(start=False):
            run = workflow().run_flow(
                data,
                config=workflow.config_class(**config),
                autosave_dir=results,
                strict=False,
            )
        figure, _ = WorkflowGraph(run).get_plot()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        figure.savefig(path, dpi=100, bbox_inches="tight")
        wx.CallAfter(self.next)

    # --- tables and results ---

    def table(self, spec):
        return self.data if spec == "data" else spec(self.data)

    def tables(self, inputs: dict) -> dict:
        return {name: self.table(spec) for name, spec in inputs.items()}

    def run(self, name, config, inputs=None):
        """A tool's results; ``inputs``: its tables by name, or a function of the data
        that makes its one input table."""
        key = (name, config.model_dump_json(), repr(inputs))
        if key not in self.results:
            if callable(inputs):
                tables = [inputs(self.data)]
            else:
                tables = list(self.tables(inputs).values()) if inputs else [self.data]
            tool = tools.get(name)
            if tool.inputs and tool.inputs[0].many:
                tables = [tables]
            self.results[key] = tool()(*tables, config=config)
        return self.results[key]

    # --- other dialogs of the application ---

    def open_dialog(self):
        from flim.core.settings import AppSettings
        from flim.gui.importdlg import ImportDlg

        return ImportDlg(
            self.frame,
            "Open File",
            AppSettings.default(),
            parsefname=False,
            preprocess=False,
            singlefile=True,
        )

    def import_dialog(self):
        from flim.core.settings import AppSettings
        from flim.gui.importdlg import ImportDlg

        settings = AppSettings.default()
        settings.import_.filename_parser.parser = "fov_treatment_cell_parser"
        settings.import_.filename_parser.patterns = []  # the parser's own
        dialog = ImportDlg(self.frame, "Import File(s)", settings)
        # as after Add Files (the files don't exist here)
        dialog.files_list.Set(
            [
                f"/data/9SR/Results-{f}-{t}_{c:02d}.txt"
                for f in ("a", "b")
                for t in TREATMENTS
                for c in (1, 2)
            ]
        )
        return dialog

    def category_filter(self):
        from flim.gui.dialogs import SelectGroupsDlg

        from flim.gui.datapanel import category_values

        values = category_values(self.data["Treatment"])  # as the data window
        return SelectGroupsDlg(
            self.frame,
            title="Treatment: Select Items",
            groups=values,
            selected=["ctrl", "Dox30", "Dox60"],
        )

    def filter_settings(self):
        from flim.core.settings import AppSettings
        from flim.gui.dialogs import ConfigureFiltersDlg

        filters = AppSettings.default().filters
        filters.use = True
        return ConfigureFiltersDlg(self.frame, filters, self.data, {})

    def pivot_groups(self):
        from flim.gui.dialogs import SelectGroupsDlg

        return SelectGroupsDlg(
            self.frame,
            title="Pivot data: Groups to pivot",
            groups=CATEGORIES,
            selected=["Treatment"],
        )

    def pivot_columns(self):
        from flim.gui.dialogs import SelectGroupsDlg

        columns = [c for c in self.data.columns if c not in CATEGORIES]
        return SelectGroupsDlg(
            self.frame,
            title="Pivot data: Columns to retain",
            groups=columns,
            selected=["FAD a1[%]", "NAD(P)H a2[%]"],
        )

    # --- dialog setups ---

    def show_treatment_order(self, dialog):
        """Order Categories: Treatment selected and checked, its values shown."""
        editor = dialog.fields.editors["categories"]
        index = editor.columns.FindString("Treatment")
        editor.columns.Check(index)
        editor.columns.SetSelection(index)
        editor._on_column(None)
        dialog.validate()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    names = argv[1:] or list(SHOTS)
    unknown = [n for n in names if n not in SHOTS]
    if unknown:
        print(f"Unknown screenshots: {', '.join(unknown)}")
        return 2
    app = wx.App(False)
    shooter = Shooter(load(argv[0]), names)
    wx.CallLater(DELAY, shooter.next)
    app.MainLoop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
