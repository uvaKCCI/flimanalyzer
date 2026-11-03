import gc
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def flim_data():
    """Small synthetic FLIM table: 2 treatments x 3 FOVs x 10 cells."""
    rng = np.random.default_rng(0)
    rows = []
    for treatment, offset in (("WT", 0.0), ("KO", 100.0)):
        for fov in ("1", "2", "3"):
            for cell in range(10):
                a1 = rng.uniform(60, 80)
                rows.append(
                    {
                        "Treatment": treatment,
                        "FOV": fov,
                        "Cell": str(cell),
                        "NAD(P)H t1": rng.normal(400 + offset, 20),
                        "NAD(P)H t2": rng.normal(3000 + offset, 100),
                        "NAD(P)H a1[%]": a1,
                        "NAD(P)H a2[%]": 100.0 - a1,
                        "FAD a1[%]": rng.uniform(20, 40),
                        "FAD photons": rng.integers(80, 200),
                    }
                )
    df = pd.DataFrame(rows)
    for col in ("Treatment", "FOV", "Cell"):
        df[col] = df[col].astype("category")
    return df


@pytest.fixture
def flirr_data(flim_data):
    """flim_data with a FLIRR column, for the Basic FLIRR workflow."""
    df = flim_data.copy()
    df["FLIRR"] = df["NAD(P)H a2[%]"] / df["FAD a1[%]"]
    return df


@pytest.fixture
def features():
    return ["NAD(P)H t1", "NAD(P)H t2", "NAD(P)H a1[%]"]


@pytest.fixture(scope="session")
def prefect_harness():
    """One temporary Prefect server and database for the whole session; nothing is
    reported to a real server. Started by the first test that needs it."""
    from prefect.testing.utilities import prefect_test_harness

    with prefect_test_harness():
        yield


@pytest.fixture(scope="session")
def wxapp():
    """One wx app for all GUI tests: wxPython supports one per process."""
    wx = pytest.importorskip("wx")
    try:
        app = wx.App()
    except SystemExit:  # raised by wx when no display is available
        pytest.skip("no display available")
    import flim.gui  # noqa: F401  (configures wx and matplotlib for the GUI)

    return app


@pytest.fixture
def data_choices(table):
    """The input tables offered by the dialogs of ``dialog`` (``table``: the test
    module's)."""
    return {"Table: data": table}


@pytest.fixture
def dialog(wxapp, data_choices):
    """Makes configuration dialogs of tools (by name); destroyed after the test."""
    from flim.core.registry import tools
    from flim.gui.configdialog import ConfigDialog

    dialogs = []

    def make(name, config=None, **kwargs):
        kwargs.setdefault("data_choices", data_choices)
        d = ConfigDialog(None, tools.get(name), config, **kwargs)
        dialogs.append(d)
        return d

    yield make
    for d in dialogs:
        d.Destroy()


@pytest.fixture(autouse=True, scope="module")
def destroy_windows():
    """Destroys the windows a test module left open."""
    yield
    wx = sys.modules.get("wx")
    if wx is not None and wx.GetApp() is not None:
        for window in list(wx.GetTopLevelWindows()):
            # windows already destroyed by a test may still be listed until deleted
            if window and not window.IsBeingDeleted():
                window.Destroy()


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")
    # collect leftovers (e.g. wx objects kept alive by a failed test's traceback)
    # here, on the main thread, not later in some worker thread
    gc.collect()

