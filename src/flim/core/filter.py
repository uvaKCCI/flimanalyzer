#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Range filters for table columns."""

import logging
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


class Filter:
    """Base class of filters: a name, whether it is selected, parameters, a text.

    The base filter keeps all rows.

    Args:
        name: The filter's name; None for `Basic Filter`.
        selected: Whether the filter is selected (used). Defaults to False.
        params: The filter's parameters.
        descr: The filter's description.
    """

    def __init__(
        self,
        name: Optional[str],
        selected: bool = False,
        params: Optional[dict[str, Any]] = None,
        descr: str = "",
    ) -> None:
        """Create a filter; see the class for the arguments."""
        if name is None:
            self.name = "Basic Filter"
        else:
            self.name = name
        self.selected = selected
        self.parameters = params
        self.description = descr

    def set_params(self, params: Optional[dict[str, Any]]) -> None:
        """Replace the filter's parameters."""
        self.parameters = params

    def set_parameter_item(self, key: str, value: Any) -> None:
        """Set one parameter; the filter must have a parameters dict."""
        self.parameters[key] = value

    def set_name(self, newname: Optional[str]) -> None:
        """Rename the filter; None or an empty name leaves the name as it is."""
        if newname is not None and len(newname) > 0:
            self.name = newname

    def get_name(self) -> str:
        """Return the filter's name."""
        return self.name

    def get_description(self) -> str:
        """Return the filter's description, or `Not provided.` if it is None."""
        if self.description is None:
            return "Not provided."
        else:
            return self.description

    def get_params(self) -> Optional[dict[str, Any]]:
        """Return the filter's parameters."""
        return self.parameters

    def select(self, sel: bool = True) -> None:
        """Select the filter (use it), or with `sel` False deselect it."""
        self.selected = sel

    def is_selected(self) -> bool:
        """Return whether the filter is selected."""
        return self.selected

    def apply(self, data: "pd.DataFrame") -> "pd.DataFrame":
        """Return the table filtered; the base filter returns it unchanged."""
        return data

    def get_dropped(self, data: "pd.DataFrame") -> np.ndarray | list[int]:
        """Return the rows the filter drops; the base filter drops none."""
        return []


class RangeFilter(Filter):
    """A filter that drops the rows whose value in a column is outside a range.

    The range is inclusive: rows with values from `rangelow` to `rangehigh` are kept.

    Args:
        name: The column the filter applies to.
        rangelow: The lowest value kept.
        rangehigh: The highest value kept.
        allowedmin: The lowest value `rangelow` may have; None for no limit.
        allowedmax: The highest value `rangehigh` may have; None for no limit.
        selected: Whether the filter is selected (used). Defaults to False.
        dropna: Whether rows with a missing value in the column are dropped too.
            Defaults to True.
        params: The parameters as a dict (see `set_params`); if given, the other
            arguments are ignored.
    """

    def __init__(
        self,
        name: str = "",
        rangelow: float = 0,
        rangehigh: float = 100,
        allowedmin: Optional[float] = None,
        allowedmax: Optional[float] = None,
        selected: bool = False,
        dropna: bool = True,
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        """Create a range filter; see the class for the arguments."""
        super().__init__(name, selected)  # the base attributes, e.g. `description`
        if params:
            self.set_params(params)
        else:
            self.name = name
            self.allowedmin = allowedmin
            self.allowedmax = allowedmax
            self.rangelow = rangelow
            self.rangehigh = rangehigh
            self.set_allowed(allowedmin, allowedmax)
            self.set_range(rangelow, rangehigh)
            self.selected = selected
            self.dropna = dropna

    def get_params(self) -> dict[str, Any]:
        """Return the parameters: name, range, allowed limits, selected, dropna."""
        return {
            "name": self.name,
            "rangelow": self.rangelow,
            "rangehigh": self.rangehigh,
            "allowedmin": self.allowedmin,
            "allowedmax": self.allowedmax,
            "selected": self.selected,
            "dropna": self.dropna,
        }

    def set_params(self, params: dict[str, Any]) -> None:
        """Set the filter from parameters as returned by `get_params`.

        Missing keys take these values: name "", range 0 to 100, no allowed limits,
        `selected` True, `dropna` True. `selected` is True here, unlike the
        constructor's default (False, for a new filter): stored parameters without it
        were written by versions that applied every filter they listed, and the
        conversions of settings files read them the same way
        (`flim.core.filtering`, `flim.configs.data`).

        Args:
            params: The parameters.
        """
        self.name = params.get("name", "")
        self.rangelow = params.get("rangelow", 0)
        self.rangehigh = params.get("rangehigh", 100)
        self.allowedmin = params.get("allowedmin", None)
        self.allowedmax = params.get("allowedmax", None)
        self.selected = params.get("selected", True)
        self.dropna = params.get("dropna", True)
        self.set_allowed(self.allowedmin, self.allowedmax)
        self.set_range(self.rangelow, self.rangehigh)

    def clip_range(self) -> tuple[float, float]:
        """Clip the range to the allowed minimum and maximum, where they are set.

        Returns:
            The range, (low, high).
        """
        if self.allowedmin is not None and self.rangelow < self.allowedmin:
            self.rangelow = self.allowedmin
        if self.allowedmax is not None and self.rangehigh > self.allowedmax:
            self.rangehigh = self.allowedmax
        return self.rangelow, self.rangehigh

    def set_range(self, low: float, high: float) -> tuple[float, float]:
        """Set the range, then clip it (see `clip_range`).

        Returns:
            The range after clipping, (low, high).
        """
        self.rangelow = low
        self.rangehigh = high
        return self.clip_range()

    def set_rangelow(self, low: float) -> None:
        """Set the lower end of the range (see `set_range`)."""
        self.set_range(low, self.rangehigh)

    def set_rangehigh(self, high: float) -> None:
        """Set the upper end of the range (see `set_range`)."""
        self.set_range(self.rangelow, high)

    def get_range(self) -> tuple[float, float]:
        """Return the range, (low, high)."""
        return self.rangelow, self.rangehigh

    def get_rangelow(self) -> float:
        """Return the lower end of the range."""
        return self.rangelow

    def get_rangehigh(self) -> float:
        """Return the upper end of the range."""
        return self.rangehigh

    def is_identical_range(self, rlow: float, rhigh: float) -> bool:
        """Return whether the filter's range is (`rlow`, `rhigh`)."""
        return rlow == self.rangelow and rhigh == self.rangehigh

    def set_allowed(self, mina: Optional[float], maxa: Optional[float]) -> None:
        """Set the allowed limits of the range, then clip the range.

        If both limits are given and the minimum is greater than the maximum, they
        are swapped.

        Args:
            mina: The allowed minimum; None for no limit.
            maxa: The allowed maximum; None for no limit.
        """
        self.allowedmin = mina
        self.allowedmax = maxa
        if mina is not None and maxa is not None and mina > maxa:
            self.allowedmin = maxa
            self.allowedmax = mina
        self.clip_range()

    def get_dropped(self, data: "pd.DataFrame") -> np.ndarray | list[int]:
        """Return the positions of the rows whose value is outside the range.

        With `dropna`, rows with a missing value are included too. The filter's
        selected state is not checked.

        Args:
            data: The table.

        Returns:
            The row positions; an empty list if the table has no column of the
            filter's name.
        """
        if self.name not in data.columns.values:
            return []
        low, high = self.get_range()
        logger.debug(f"{self.is_selected()}, filtering {self.name}: {low}, {high}")
        droppedrows = []
        if self.dropna:
            droppedrows = np.flatnonzero(
                (data[self.name] != data[self.name])
                | (data[self.name] > high)
                | (data[self.name] < low)
            )
        else:
            droppedrows = np.flatnonzero(
                (data[self.name] > high) | (data[self.name] < low)
            )
        logger.debug(f"dropped rows: {droppedrows}")
        return droppedrows
