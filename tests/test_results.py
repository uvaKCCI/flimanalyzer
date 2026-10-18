import joblib
import matplotlib.pyplot as plt
import pandas as pd

from flim.results import save_results


def _figure():
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3])
    return fig


def test_figures_are_saved_as_png_but_not_pickled(tmp_path):
    table = pd.DataFrame({"a": [1, 2]})
    save_results({"Table: A": table, "Plot: B": _figure(), "Model File": "m.model"}, str(tmp_path), "Task")
    assert (tmp_path / "Table_A.txt").exists()
    assert (tmp_path / "Plot_B.png").exists()
    pickled = joblib.load(tmp_path / "pickled" / "Task")
    assert set(pickled) == {"Table: A", "Model File"}
    pd.testing.assert_frame_equal(pickled["Table: A"], table)


def test_result_with_only_figures_writes_no_pickle(tmp_path):
    save_results({"Plot: B": _figure()}, str(tmp_path), "Plots")
    assert (tmp_path / "Plot_B.png").exists()
    assert not (tmp_path / "pickled").exists()


def test_non_dict_results(tmp_path):
    table = pd.DataFrame({"a": [1, 2]})
    save_results(table, str(tmp_path), "Data")
    pd.testing.assert_frame_equal(joblib.load(tmp_path / "pickled" / "Data"), table)
    save_results(_figure(), str(tmp_path / "fig"), "Figure")
    assert not (tmp_path / "fig" / "pickled").exists()
