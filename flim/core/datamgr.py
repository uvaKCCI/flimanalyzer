"""The DataManager: the single authority for the items the GUI shows (tables, plots).

Each item has an ID, its data type, a title (a display label, unique among the open
items), its value, and whether it is modified (has changes not saved to a file) and
open. Sources add items through the manager (File > Open, Import, tool results);
windows are views that report their edits to it. Items are identified by their ID,
not by their title, so two items can never be mistaken for each other (e.g. two files
of the same name from different folders).
"""

import itertools
import logging
import threading
from dataclasses import dataclass, replace
from typing import Any, Literal, Optional

from flim.core.observe import Observable
from flim.core.types import DataType

logger = logging.getLogger(__name__)

ItemId = int


@dataclass(frozen=True)
class Item:
    """An item of the DataManager, as of one moment (changes make a new Item).

    Attributes:
        id: The item's ID, never reused within a session.
        data_type: Its data type, e.g. `TableType`; None if no data type accepts the
            value.
        title: Its display label, unique among the open items.
        value: Its value, e.g. a DataFrame or a Figure.
        modified: Whether it has changes not saved to a file.
        open: Whether it is open (shown).
        source: Where it came from, e.g. a file path or a tool's name.
    """

    id: ItemId
    data_type: Optional[type[DataType]]
    title: str
    value: Any
    modified: bool = False
    open: bool = True
    source: Optional[str] = None


@dataclass(frozen=True)
class Change:
    """A change message: which item changed, and how.

    Attributes:
        kind: `added`, `renamed`, `modified` (the modified state changed), `value` (the
            value was replaced) or `closed`.
        item: The item after the change.
    """

    kind: Literal["added", "renamed", "modified", "value", "closed"]
    item: Item


class DataManager(Observable):
    """The items of a session: one manager per instance (GUI), the single authority.

    All changes go through it, one at a time; each sends a `Change` to the
    subscribers. Readers get items (`Item`), which do not change.
    """

    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()
        self._items: dict[ItemId, Item] = {}
        self._ids = itertools.count(1)

    # --- reading ---

    def get(self, item_id: ItemId) -> Item:
        """Return an item.

        Raises:
            KeyError: If there is no item with this ID.
        """
        with self._lock:
            return self._items[item_id]

    def items(self, open_only: bool = True) -> list[Item]:
        """Return the items, in the order they were added.

        Args:
            open_only: Only the open items.
        """
        with self._lock:
            return [i for i in self._items.values() if i.open or not open_only]

    def find(self, title: str) -> Optional[Item]:
        """Return the open item with a title, or None."""
        with self._lock:
            return next((i for i in self.items() if i.title == title), None)

    def unique_title(self, title: str, exclude: Optional[ItemId] = None) -> str:
        """Return a title no other open item has: `title`, else `title-1`, `title-2`, ...

        Args:
            title: The wanted title.
            exclude: An item whose own title does not count (when renaming it).
        """
        with self._lock:
            taken = {i.title for i in self.items() if i.id != exclude}
        candidate, number = title, 1
        while candidate in taken:
            candidate = f"{title}-{number}"
            number += 1
        return candidate

    def snapshot(self, item_id: ItemId) -> Any:
        """Return a copy of an item's value for a run, which the item's later edits
        do not change (see `DataType.snapshot`)."""
        item = self.get(item_id)
        if item.data_type is None:
            return item.value
        return item.data_type.snapshot(item.value)

    # --- changing ---

    def add(
        self,
        value: Any,
        title: str,
        *,
        modified: bool = False,
        source: Optional[str] = None,
    ) -> Item:
        """Add an item; its title is made unique among the open items.

        Args:
            value: The value, e.g. a DataFrame.
            title: The wanted title.
            modified: Whether it has changes not saved to a file (e.g. a tool's result
                that was not saved).
            source: Where it came from, e.g. a file path or a tool's name.

        Returns:
            The new item.
        """
        with self._lock:
            item = Item(
                id=next(self._ids),
                data_type=DataType.of(value),
                title=self.unique_title(title),
                value=value,
                modified=modified,
                source=source,
            )
            self._items[item.id] = item
        logger.debug(f"Item {item.id} added: {item.title}")
        self.notify(Change("added", item))
        return item

    def _change(self, item_id: ItemId, kind, **changes) -> Item:
        with self._lock:
            item = replace(self._items[item_id], **changes)
            self._items[item_id] = item
        self.notify(Change(kind, item))
        return item

    def rename(self, item_id: ItemId, title: str) -> Item:
        """Give an item a new title, made unique among the other open items."""
        return self._change(item_id, "renamed", title=self.unique_title(title, item_id))

    def set_modified(self, item_id: ItemId, modified: bool = True) -> Item:
        """Mark an item as modified (changed since saved) or not (saved)."""
        if self.get(item_id).modified == modified:
            return self.get(item_id)
        return self._change(item_id, "modified", modified=modified)

    def set_value(self, item_id: ItemId, value: Any, *, modified: bool = True) -> Item:
        """Replace an item's value, e.g. after an edit in its window."""
        return self._change(
            item_id, "value", value=value, data_type=DataType.of(value), modified=modified
        )

    def close(self, item_id: ItemId) -> Item:
        """Close an item: it is no longer open, and its value is released."""
        return self._change(item_id, "closed", open=False, value=None)
