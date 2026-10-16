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
def features():
    return ["NAD(P)H t1", "NAD(P)H t2", "NAD(P)H a1[%]"]


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")
