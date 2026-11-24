"""Regenerates the screenshots of the user guide (docs/images), on macOS.

    uv run python docs/screenshots.py DATAFILE [NAME ...]

DATAFILE is a FLIM results table (tab-separated) with the columns Cell, FOV and
Treatment; the user guide uses 9SR-Mito-ChiFilter.txt. Its Directory and File
columns are not shown. NAMEs (image paths below docs/images, e.g.
analysis/gmm-config.png) select screenshots; default: all.

Dialogs and windows are captured by their window number (``screencapture -l``: only
their own content, never other windows; the terminal needs the Screen Recording
permission), plots are saved directly. Windows open on the screen while it runs. The runs use a
temporary Prefect server, whatever server the Prefect profile names.
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
from flim.core.config import Processing, ProcessingRules  # noqa: E402
from flim.configs import (  # noqa: E402
    ConcatConfig,
    FilterConfig,
    FLIRRPlotConfig,
    FuseCategoriesConfig,
    GMMConfig,
    HistogramConfig,
    MergeConfig,
    PairPlotConfig,
    PivotConfig,
    ScaleConfig,
    SeparateCategoriesConfig,
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
from flim.configs.workflow import AEFeatureConfig  # noqa: E402
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
DATAFILE = "9SR-Mito-ChiFilter.txt"
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


def with_source(data):
    """The data as a read table has it: `Source`, `Directory` and `File` first."""
    from pathlib import PurePosixPath

    file = PurePosixPath("/data/flim") / DATAFILE  # a neutral path, not the user's
    columns = {"Source": file.as_uri(), "Directory": str(file.parent), "File": file.name}
    return pd.concat([pd.DataFrame(columns, index=data.index), data], axis=1)



def raw_names(data):
    """The data with the column names of the FLIM software, before Rename Columns:
    `trp t1` as `Exc1_-Ch1-_t1` and so on (the Rename Columns and Drop Columns
    examples)."""
    prefixes = {"trp ": "Exc1_-Ch1-_", "NAD(P)H ": "Exc1_-Ch2-_", "FAD ": "Exc2_-Ch3-_"}

    def raw(name):
        for new, old in prefixes.items():
            if name.startswith(new):
                return old + name[len(new):]
        return name

    return data.rename(columns=raw)


def with_unused_channel(data):
    """The renamed data with columns of a channel that is not renamed (`Exc3_`), as
    Drop Columns' default rows remove them."""
    extra = {f"Exc3_-Ch4-_{c}": data[f"FAD {c}"] for c in ("a1", "t1", "chi")}
    return pd.concat([data, pd.DataFrame(extra, index=data.index)], axis=1)


def legacy_columns(data):
    """The data as FLIMAnalyzer 0.6 read it: `Directory` and `File`, no `Source`."""
    return with_source(data).drop(columns=["Source"])

# --- the screenshots: image path -> (kind, arguments) ---
# kinds: "main" (the main window), "dialog" (a tool's configuration dialog), "table"
# (a data window), "window" (another dialog of the GUI, made by a method of the
# shooter), "plot" (a figure of a tool's results), "graph" (the graph of a workflow
# run), "plotwindow" (a plot window with its toolbar), "progress" (the progress
# dialog of a workflow run)
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
HISTOGRAM_CUMULATIVE = HISTOGRAMS[2].model_copy(update={"cumulative": True})  # step style
FLIRR = FLIRRPlotConfig(grouping=["Treatment", "FOV"])
FILTER = FilterConfig(
    features={"filters": [
        {"column": "FAD a1[%]", "low": 50, "high": 90},
        {"column": "FLIRR", "high": 2.4},
    ]},
    categories={"filters": [{"kind": "category", "column": "Treatment", "keep": ["ctrl", "Dox15", "Dox30"]}]},
    other={"filters": [{"kind": "expression", "expression": "FLIRR > 0.1"}]},
)  # fmt: skip
SORT = SortConfig(features=["FAD a1"])
# runs of workflows use the closest column for a column that the data does not have
GUESSES = ProcessingRules.of(Processing(strict=False))

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
BOX_SINGLE = BoxPlotConfig(
    grouping=["Treatment", "FOV"],
    features=["FAD a1[%]", "NAD(P)H a2[%]", "FLIRR"],
    single_figure=True,
    plots_per_row=3,
)

PIVOT = PivotConfig(grouping=["Treatment"], features=["FAD a1[%]", "NAD(P)H a2[%]"])
pivoted = result_of("Pivot", PIVOT)  # the Pivot example's table, `Table: Pivoted`
SPLIT = SplitConfig(grouping=["FOV"])
MERGE = MergeConfig(how="left", on=CATEGORIES)
SCALE = ScaleConfig(features=["FAD a1[%]", "NAD(P)H a2[%]", "FLIRR"])
FUSE = FuseCategoriesConfig(grouping=["Treatment", "FOV"])
# the fused column `Treatment:FOV` without the original columns, so Separate Categories
# can give its parts their names back
fused = result_of("Fuse Categories", FUSE.model_copy(update={"keep_original": False}))
SEPARATE = SeparateCategoriesConfig(column="Treatment:FOV", names=["Treatment", "FOV"])
FEATURE_ANALYSIS = AEFeatureConfig(control_group="ctrl")  # the data's control group
FOV_A = fov("a")  # the workflow examples: the same steps, faster
TWO_FILES = {"example1.txt": FOV_A, "example2.txt": fov("b")}
MERGE_INPUTS = {DATAFILE: "data", "Table: Summary": fad_a1_means}

SHOTS = {
    "toolbar.png": ("main", {}),
    "data/exdata_table.png": ("table", {}),
    "data/dataframe.png": ("table", {}),
    "data/source-columns.png": ("table", {"table": with_source, "size": (1000, 300)}),
    # Data
    "data/precision.png": ("table", {"crop": (400, 28, 1000, 250)}),  # decimals next to the control
    "data/category-filter.png": ("window", {"make": "category_filter"}),
    "data/filter-settings.png": ("window", {"make": "filter_settings"}),
    "data/sort-preresult.png": ("table", {}),
    "data/filtertool-config.png": ("dialog", {"tool": "Filter", "config": FILTER}),
    "data/sort-config.png": ("dialog", {"tool": "Sort", "config": SORT}),
    "data/sort-results.png": ("table", {"tool": "Sort", "config": SORT}),
    "data/order-config.png": ("dialog", {"tool": "Order Category Values", "setup": "show_treatment_order"}),
    "data/concat-config1.png": ("dialog", {"tool": "Concatenate", "config": ConcatConfig(), "inputs": TWO_FILES, "selected": [list(TWO_FILES)]}),
    "data/split-input.png": ("dialog", {"tool": "Split", "config": SPLIT}),
    "data/split-result.png": ("table", {"tool": "Split", "config": SPLIT, "result": "FOV=a"}),
    "data/merge-start.png": ("table", {}),
    "data/merge-summary.png": ("table", {"table": fad_a1_means, "title": "Table: Summary"}),
    "data/merge-dialog.png": ("dialog", {"tool": "Merge", "config": MERGE, "inputs": MERGE_INPUTS, "selected": list(MERGE_INPUTS)}),
    "data/merge-res1.png": ("table", {"tool": "Merge", "config": MERGE, "inputs": MERGE_INPUTS}),
    "data/merge-res3.png": ("table", {"tool": "Merge", "config": MERGE, "inputs": MERGE_INPUTS, "scroll_to_end": True}),
    "data/pivot-original.png": ("table", {}),
    "data/pivot-result.png": ("table", {"tool": "Pivot", "config": PIVOT}),
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
    "analysis/relpivot-result.png": ("table", {"tool": "Pivot", "config": PIVOT}),
    "analysis/seriesanalysis-config.png": ("dialog", {"tool": "Series Analysis", "config": SERIES, "inputs": {"Table: Pivoted": pivoted}}),
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
    "analysis/histogram-cumulative.png": ("plot", {"tool": "Frequency Histogram", "config": HISTOGRAM_CUMULATIVE}),
    "analysis/histogram-results1a.png": ("table", {"tool": "Frequency Histogram", "config": HISTOGRAMS[0]}),
    "analysis/barplot-config-grouping.png": ("dialog", {"tool": "Bar Plot", "config": BAR[0]}),
    "analysis/barplot-result1-grouping.png": ("plot", {"tool": "Bar Plot", "config": BAR[0]}),
    "analysis/barplot-result2-grouping.png": ("plot", {"tool": "Bar Plot", "config": BAR[1]}),
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
    "analysis/workflow-results.png": ("graph", {"tool": "Basic FLIRR Analysis", "config": FLIRR_WORKFLOW, "rows": FOV_A}),
    "analysis/flirr_data.png": ("table", {}),
    "analysis/flirr-config.png": ("dialog", {"tool": "FLIRR Plot", "config": FLIRR}),
    "analysis/flirr-result.png": ("plot", {"tool": "FLIRR Plot", "config": FLIRR}),
    "analysis/pairplot-config.png": ("dialog", {"tool": "Pair Plot", "config": PAIRPLOT}),
    "analysis/pairplot-results.png": ("plot", {"tool": "Pair Plot", "config": PAIRPLOT}),
    # tool dialogs, autoencoders, single figure, plot window, runs
    "dialogs/tool-dialog.png": ("dialog", {"tool": "K-Means", "config": KMEANS, "setup": "expand_resources"}),
    "analysis/aetrain-config.png": ("dialog", {"tool": "Autoencoder Train"}),
    "analysis/boxplot-config-single.png": ("dialog", {"tool": "Box Plot", "config": BOX_SINGLE}),
    "analysis/boxplot-result-single.png": ("plot", {"tool": "Box Plot", "config": BOX_SINGLE}),
    "analysis/plotwindow.png": ("plotwindow", {"tool": "Box Plot", "config": BOX[0]}),
    "analysis/plot-setaxis.png": ("window", {"make": "axis_dialog"}),
    "analysis/workflow-progress.png": ("progress", {"tool": "Basic FLIRR Analysis", "config": FLIRR_WORKFLOW}),
    "analysis/workflow-summary.png": ("window", {"make": "run_summary"}),
    # dialogs of the tools that had none (2026-11-24): every tool in a menu has one
    "data/rename-config.png": ("dialog", {"tool": "Rename Columns", "inputs": {DATAFILE: raw_names}}),
    "data/drop-config.png": ("dialog", {"tool": "Drop Columns", "inputs": {DATAFILE: with_unused_channel}}),
    "analysis/calculate-config.png": ("dialog", {"tool": "Calculate"}),
    "analysis/scale-config.png": ("dialog", {"tool": "Scale", "config": SCALE}),
    "data/fuse-config.png": ("dialog", {"tool": "Fuse Categories", "config": FUSE}),
    "data/separate-config.png": ("dialog", {"tool": "Separate Categories", "config": SEPARATE, "inputs": {"Table: Fused": fused}}),
    "data/source-config.png": ("dialog", {"tool": "Directory/File to Source", "inputs": {DATAFILE: legacy_columns}}),
    "data/pivot-config.png": ("dialog", {"tool": "Pivot", "config": PIVOT}),
    "data/unpivot-config.png": ("dialog", {"tool": "Unpivot", "inputs": {"Table: Pivoted": pivoted}}),
    "analysis/aerun-config.png": ("dialog", {"tool": "Autoencoder Run"}),
    "analysis/aeaugment-config.png": ("dialog", {"tool": "Autoencoder Augment Data"}),
    "data/import-config.png": ("dialog", {"tool": "Import Tables"}),
    "workflow/import-config.png": ("dialog", {"tool": "Import"}),
    "workflow/flirr-config.png": ("dialog", {"tool": "Basic FLIRR Analysis"}),
    "workflow/aetune-config.png": ("dialog", {"tool": "FLIM Data Augmentation Tuning"}),
    "workflow/aefeature-config.png": ("dialog", {"tool": "FLIM Feature Analysis", "config": FEATURE_ANALYSIS}),
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
    """Brings this program to the front, so that its windows are drawn active."""
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

        # the built-in workflow files, as the app registers them at startup (e.g. for
        # the Workflow choice of Import Tables)
        from flim.core.workflowfile import register_workflow_files

        register_workflow_files(log=False)
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
        # the data under its file name, as the table windows show it
        choices = self.tables(inputs or {DATAFILE: "data"})
        from flim.core.execution import ExecutionOptions
        from flim.core.saving import AutosaveConfig
        from flim.core.workflow import Workflow

        # as the GUI opens it: a workflow's `Save results` is checked and locked, in the
        # results folder (~/FLIMAnalyzerResults, shown without the user's home)
        locked = issubclass(tool, Workflow)
        execution = None
        if locked:
            autosave = AutosaveConfig(enabled=True, results_dir="~/FLIMAnalyzerResults")
            execution = ExecutionOptions(autosave=autosave)
        dialog = dialog_class(tool.config_class)(
            self.frame, tool, config, data_choices=choices, selected=selected,
            execution=execution, autosave_locked=locked,
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
        """The graph of a workflow run, as the GUI shows it after the run."""
        from flim.core.graph import WorkflowGraph

        figure, _ = WorkflowGraph(self.flow_run(tool, config, rows)).get_plot()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        figure.savefig(path, dpi=100, bbox_inches="tight")
        wx.CallAfter(self.next)

    def _plotwindow(self, path, tool, config, inputs=None):
        """A plot window, with its toolbar."""
        from flim.gui.plotframe import PlotFrame

        results = self.run(tool, config, inputs)
        title, figure = next(
            (k, v) for k, v in results.items() if isinstance(v, matplotlib.figure.Figure)
        )
        window = PlotFrame(self.frame, figure, title)
        window.Show()
        self._later(window, path)

    def _progress(self, path, tool, config):
        """The progress dialog of a workflow run, its task list open, while it runs."""
        from flim.core.prefect_server import use_prefect_server
        from flim.gui.progressdlg import RunProgressDialog

        workflow = tools.get(tool)

        def start_run(cancel_token, on_progress, on_start):
            with use_prefect_server(start=False):
                return workflow().run_flow(
                    self.data,
                    config=workflow.config_class(**config),
                    autosave_dir=self.results_folder(),
                    on_progress=on_progress,
                    cancel_token=cancel_token,
                    on_start=on_start,
                    processing=GUESSES,
                )

        dialog = RunProgressDialog(self.frame, tool, start_run)

        def shoot():
            if not dialog or not dialog.IsModal():  # the run has already ended
                print("  failed: the run ended before the capture")
                return
            dialog.tasks_pane.Expand()
            dialog.Fit()
            _activate()
            _make_key(dialog)
            wx.CallLater(500, lambda: (capture(dialog, path), dialog.OnCancel(None)))

        wx.CallLater(4 * DELAY, shoot)
        dialog.ShowModal()  # until the run is cancelled
        dialog.Destroy()
        wx.CallAfter(self.next)

    # --- tables and results ---

    def results_folder(self):
        import tempfile

        if getattr(self, "_results_folder", None) is None:
            self._results_folder = tempfile.mkdtemp(prefix="flim-screenshots-")
        return self._results_folder

    def flow_run(self, tool, config, rows=None):
        """A workflow's run (of ``rows`` of the data), made once."""
        from flim.core.prefect_server import use_prefect_server

        key = ("run", tool, repr(config), repr(rows))
        if key not in self.results:
            workflow = tools.get(tool)
            with use_prefect_server(start=False):
                self.results[key] = workflow().run_flow(
                    self.table(rows or "data"),
                    config=workflow.config_class(**config),
                    autosave_dir=self.results_folder(),
                    processing=GUESSES,
                )
        return self.results[key]

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

    # --- other dialogs of the GUI ---

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
        from flim.core.filtering import window_filters
        from flim.core.settings import AppSettings
        from flim.gui.dialogs import ConfigureFiltersDlg

        filters = window_filters(AppSettings.default())  # as a new table window
        filters.features.enabled = True  # Filter Features on
        # Filter Features..., with the preset buttons, as a table window opens it
        return ConfigureFiltersDlg(
            self.frame, filters, self.data, {}, presets=self.frame.filter_presets()
        )

    def axis_dialog(self):
        from flim.gui.dialogs import ConfigureAxisDlg

        return ConfigureAxisDlg(
            self.frame, "Set Y Axis", {"label": "FLIRR", "min": 0.0, "max": 0.6}
        )

    def run_summary(self):
        from flim.gui.progressdlg import RunSummaryDialog

        tool = "Basic FLIRR Analysis"
        return RunSummaryDialog(self.frame, tool, self.flow_run(tool, FLIRR_WORKFLOW, FOV_A))

    # --- dialog setups ---

    def expand_resources(self, dialog):
        """The collapsed Resources section opened."""
        from flim.gui.editors import relayout

        editor = dialog.fields.editors["resources"]
        editor.pane.Expand()
        relayout(editor.pane)

    def show_treatment_order(self, dialog):
        """Order Category Values: Treatment selected and checked, its values shown."""
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
    # a temporary Prefect server, as the tests use: the runs never reach the server of
    # the user's Prefect profile, and the run summary shows no server address
    from prefect.testing.utilities import prefect_test_harness

    with prefect_test_harness():
        app = wx.App(False)
        shooter = Shooter(load(argv[0]), names)
        wx.CallLater(DELAY, shooter.next)
        app.MainLoop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
