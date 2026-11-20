"""The DataManager (flim.core.datamgr): items by ID, titles, states, change messages."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.figure  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from flim.core.datamgr import Change, DataManager  # noqa: E402
from flim.core.types import PlotType, TableType  # noqa: E402


@pytest.fixture
def manager():
    return DataManager()


def test_items_by_id_with_unique_titles(manager):
    a = manager.add(pd.DataFrame({"x": [1]}), "data.txt", source="a/data.txt")
    b = manager.add(pd.DataFrame({"x": [2]}), "data.txt", source="b/data.txt")
    assert (a.title, b.title) == ("data.txt", "data.txt-1")
    assert a.id != b.id and a.data_type is TableType
    # the same title cannot mix up the two items (R1): each keeps its own table
    assert manager.get(a.id).value["x"].tolist() == [1]
    assert manager.get(b.id).value["x"].tolist() == [2]
    assert manager.find("data.txt-1").id == b.id


def test_states_and_messages(manager):
    messages = []
    unsubscribe = manager.subscribe(messages.append)
    figure = matplotlib.figure.Figure()
    plot = manager.add(figure, "Box Plot", modified=True)
    assert plot.data_type is PlotType and plot.modified
    manager.set_modified(plot.id, False)
    manager.set_modified(plot.id, False)  # no change: no message
    manager.rename(plot.id, "Box Plot")  # its own title does not count
    manager.close(plot.id)
    assert [m.kind for m in messages] == ["added", "modified", "renamed", "closed"]
    assert all(isinstance(m, Change) and m.item.id == plot.id for m in messages)
    closed = manager.get(plot.id)
    assert not closed.open and closed.value is None
    assert manager.items() == [] and manager.items(open_only=False) == [closed]
    # a closed item's title is free again
    assert manager.add(figure, "Box Plot").title == "Box Plot"
    unsubscribe()
    manager.add(figure, "other")
    assert len(messages) == 5  # the second add, before unsubscribing


def test_items_do_not_change(manager):
    item = manager.add(pd.DataFrame({"x": [1]}), "t")
    manager.rename(item.id, "renamed")
    assert item.title == "t" and manager.get(item.id).title == "renamed"


def test_a_snapshot_of_a_table_is_a_copy(manager):
    table = pd.DataFrame({"x": [1, 2]})
    item = manager.add(table, "t")
    snapshot = manager.snapshot(item.id)
    table.loc[0, "x"] = 99  # the window edits its table
    assert snapshot["x"].tolist() == [1, 2]


def test_set_value(manager):
    item = manager.add(pd.DataFrame({"x": [1]}), "t")
    changed = manager.set_value(item.id, pd.DataFrame({"y": [2]}))
    assert changed.modified and list(changed.value.columns) == ["y"]


def test_a_failing_subscriber_does_not_stop_the_others(manager, caplog):
    seen = []

    def fails(message):
        raise RuntimeError("boom")

    manager.subscribe(fails)
    manager.subscribe(seen.append)
    manager.add(pd.DataFrame(), "t")
    assert len(seen) == 1 and "subscriber failed" in caplog.text
