"""Calculate: the calculations as a read-only table, edited one at a time.

The table starts empty (`Calculate.dialog_config`). `Add Calculation...` and `Edit...`
open the calculation editor: a kind (expression or function), then only that kind's
fields, generated from its config; the function's parameters are generated from its
signature. `Load Preset...` adds presets that apply to the input table: the
built-in calculations and those saved with `Save as Preset...` (the user settings'
`presets` > `Calculate`, one calculation per preset). `Remove Presets...` removes
saved ones; the built-in ones can't be removed.
"""

import inspect
import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Optional

import pandas as pd
import wx
import wx.grid
from pydantic import BaseModel, ValidationError, create_model

from flim.configs.data import CalculateConfig, ExpressionCalculation, FunctionCalculation
from flim.configs.data import Calculation
from flim.core.schema import TableSchema
from flim.gui.editors import (
    CategoriesEditor,
    Editor,
    ExampleView,
    FieldErrors,
    FieldsPanel,
    _RowIssues,
    register_editor,
)

if TYPE_CHECKING:
    from flim.core.settingsmgr import SettingsManager

logger = logging.getLogger(__name__)

KINDS = {"expression": ExpressionCalculation, "function": FunctionCalculation}
_settings_manager: Optional["SettingsManager"] = None  # the session's (see bind)


def bind(settings_manager: "SettingsManager") -> None:
    """Use a session's settings for the saved presets.

    Args:
        settings_manager: The SettingsManager of the session.
    """
    global _settings_manager
    _settings_manager = settings_manager


def built_in_presets() -> list[Calculation]:
    """Return the built-in calculations: those of the import (FLIRR, NAD(P)H tm)."""
    return list(CalculateConfig().calculations)


def saved_presets() -> list[Calculation]:
    """Return the calculations saved as presets in the user settings file.

    Presets that are not valid are left out, with a warning in the log.

    Returns:
        The calculations; empty if no settings manager is bound (`bind`).
    """
    if _settings_manager is None:
        return []
    from flim.tools.data import Calculate

    presets = []
    for preset in _settings_manager.settings.tool_presets(Calculate):
        try:
            presets.extend(CalculateConfig.model_validate(preset["settings"]).calculations)
        except (KeyError, TypeError, ValueError) as err:
            logger.warning(f"Saved calculation not valid, not offered: {err}")
    return presets


def save_presets(presets: Iterable[Calculation]) -> None:
    """Replace the saved presets in the user settings file.

    Nothing is saved if no settings manager is bound (`bind`).

    Args:
        presets: The calculations.
    """
    if _settings_manager is not None:
        from flim.tools.data import Calculate

        _settings_manager.set_presets(
            Calculate,
            [
                {"name": p.name, "settings": {"calculations": [p.model_dump(mode="json")]}}
                for p in presets
            ],
        )


def describe(calculation: Calculation) -> str:
    """Return what a calculation computes, as text.

    Args:
        calculation: The calculation.

    Returns:
        An expression's text; or a function call with the argument columns and,
        after `;`, the parameters, e.g. `ratio(NAD(P)H a2[%], FAD a1[%])`.
    """
    if calculation.kind == "expression":
        return calculation.expression
    params = ", ".join(f"{k}={v:g}" for k, v in calculation.params.items())
    args = ", ".join(map(str, calculation.args)) + (f"; {params}" if params else "")
    return f"{calculation.function}({args})"


def function_summary(name: str) -> str:
    """Return a registered function's parameters and the first line of its docstring.

    Args:
        name: The function's name.

    Returns:
        The summary, e.g. ``ratio(v1, v2): Return v1 / v2; NaN if v2 is 0.``; empty
        for a name that is not registered.
    """
    import inspect

    from flim.core.calculate import FUNCTIONS, _register_builtins

    _register_builtins()
    function = FUNCTIONS.get(name)
    if function is None:
        return ""
    parameters = ", ".join(inspect.signature(function).parameters)
    doc = (inspect.getdoc(function) or "").splitlines()
    summary = doc[0].replace("`", "") if doc else ""
    return f"{name}({parameters})" + (f": {summary}" if summary else "")


# --- the editors of a function's fields ---


def _functions() -> list[str]:
    """Return the names of the registered functions, sorted."""
    from flim.core.calculate import FUNCTIONS, _register_builtins

    _register_builtins()
    return sorted(FUNCTIONS)


@register_editor(FunctionCalculation, "function")
class FunctionEditor(Editor):
    """Choice of the registered functions."""

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the drop-down of the function names; none is selected."""
        self.names = _functions()
        control = wx.Choice(parent, choices=self.names)
        control.Bind(wx.EVT_CHOICE, self.changed)
        return control

    def get(self) -> Any:
        """Return the selected function's name.

        Raises:
            ValueError: If no function is selected.
        """
        index = self.control.GetSelection()
        if index == wx.NOT_FOUND:
            raise ValueError("Choose a function")
        return self.names[index]

    def set(self, value: Any) -> None:
        """Select a function by name; a name not registered is ignored."""
        if value in self.names:
            self.control.SetSelection(self.names.index(value))


@register_editor(FunctionCalculation, "args")
class ArgumentsEditor(CategoriesEditor):
    """The function's argument columns: the input's features, checked and in order."""

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """List the input's feature columns; the checked ones stay checked."""
        self._remember()
        self.known = schema is not None and schema.complete
        self.columns = [] if schema is None else schema.by_role("feature")
        self._show()


def parameters_model(function: Optional[str]) -> Optional[type[BaseModel]]:
    """Return a model with a field per parameter with a default of a function.

    Args:
        function: The name of a registered function; None for none.

    Returns:
        A model class with a float field per parameter of the function that has a
        default (e.g. `const` of `trp_Eperc_1`), with that default; None if the
        function is not registered or has no such parameters.
    """
    from flim.core.calculate import FUNCTIONS, _register_builtins

    _register_builtins()
    func = FUNCTIONS.get(function or "")
    if func is None:
        return None
    fields = {
        name: (float, p.default)
        for name, p in inspect.signature(func).parameters.items()
        if p.default is not inspect.Parameter.empty
    }
    return create_model(f"{function} parameters", **fields) if fields else None


@register_editor(FunctionCalculation, "params")
class ParametersEditor(Editor):
    """The chosen function's parameters, one field each, with their defaults.

    The fields are rebuilt when the function changes; values of parameters that
    the new function also has are kept.
    """

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the panel; it shows `(none)` until a function has parameters."""
        self.panel = wx.Panel(parent)
        self.panel.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.function = None
        self.fields = None  # the FieldsPanel of the function's parameters
        self.values: dict = {}
        self.none = wx.StaticText(self.panel, label="(none)")
        self.panel.GetSizer().Add(self.none)
        return self.panel

    def _rebuild(self, function: Optional[str]) -> None:
        """Replace the fields with those of a function's parameters."""
        if self.fields is not None:
            self.values.update(self.get())
            self.fields.Destroy()
            self.fields = None
        self.function = function
        model = parameters_model(function)
        self.none.Show(model is None)
        if model is not None:
            self.fields = FieldsPanel(self.panel, model)
            self.fields.on_change = self.changed
            known = {k: v for k, v in self.values.items() if k in model.model_fields}
            self.fields.set_values(model(**known))
            self.panel.GetSizer().Add(self.fields, 0, wx.EXPAND)
        self.panel.Layout()

    def refresh(self, panel: FieldsPanel) -> None:
        """Rebuild the fields if the `function` field changed."""
        function = panel.value_of("function")
        if function != self.function:
            self._rebuild(function)
            panel.Layout()

    def get(self) -> Any:
        """Return the parameters' values by name; empty if there are no fields."""
        if self.fields is None:
            return {}
        model = self.fields.model
        values = self.fields.values(model())
        return {k: v for k, v in values.items() if k in model.model_fields}

    def set(self, value: Any) -> None:
        """Show parameter values (a dict by name; None for none)."""
        self.values = dict(value or {})
        self._rebuild(self.function)


# --- the calculation editor ---


SHARED = ("enabled", "name", "keep", "description")  # the fields of every kind


class CalculationDialog(wx.Dialog):
    """Dialog that edits one calculation: its kind, its shared fields, then its own.

    The fields every kind has (`SHARED`: `Use`, `New Column`, `Keep`,
    `Description`) stay in place when the kind changes; below them are the fields of
    the kind. A function's are preceded by a preview: the call with its arguments,
    and the function's parameters and summary. Below the fields, the dialog shows
    the problems of the calculation and an example from the first rows of the input
    table; OK is enabled only without errors.
    """

    def __init__(
        self,
        parent: Optional[wx.Window],
        calculation: Optional[Calculation] = None,
        columns: Iterable[Any] = (),
        schema: Optional[TableSchema] = None,
        tables: Iterable[Any] = (),
    ) -> None:
        """Build the dialog.

        Args:
            parent: The parent window.
            calculation: The calculation to edit. Defaults to None: a new
                expression.
            columns: The columns the calculation can use: the input's and those of
                the calculations before it. Defaults to none.
            schema: The input's schema (for the column choices). Defaults to None.
            tables: The input tables (for the example line). Defaults to none.
        """
        super().__init__(parent, title="Calculation", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.columns, self.schema, self.tables = list(columns), schema, list(tables)
        calculation = calculation or ExpressionCalculation()
        sizer = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(self, label="Kind"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.kind = wx.Choice(self, choices=list(KINDS))
        self.kind.SetSelection(list(KINDS).index(calculation.kind))
        self.kind.Bind(wx.EVT_CHOICE, self._on_kind)
        row.Add(self.kind)
        sizer.Add(row, 0, wx.ALL, 8)
        # the fields of every kind: built once, so they don't move with the kind
        self.shared = FieldsPanel(
            self, type(calculation), exclude=set(type(calculation).model_fields) - set(SHARED)
        )
        self.shared.set_values(calculation)
        self.shared.on_change = self.validate
        sizer.Add(self.shared, 0, wx.LEFT | wx.RIGHT, 8)  # its own width: stays in place
        # a function's call and what the function does, above its arguments
        self.preview = wx.StaticText(self, label="")
        sizer.Add(self.preview, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self.body = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.body, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self.example = ExampleView(self)
        self.message = wx.StaticText(self, label="")
        self.message.SetForegroundColour(wx.Colour(180, 0, 0))
        sizer.Add(self.example, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self.message, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        self.fields = None
        self._build(calculation)

    def _build(self, calculation: Calculation) -> None:
        """Replace the kind's own fields with those of the calculation's kind; validate."""
        if self.fields is not None:
            self.fields.Destroy()
        self.fields = FieldsPanel(
            self, type(calculation), exclude={"kind", "engine", *SHARED}
        )
        self.fields.set_schema(self.schema)
        self.fields.set_data(self.tables)
        self.fields.set_values(calculation)
        self.fields.on_change = self.validate
        self.body.Add(self.fields, 1, wx.EXPAND)
        self.validate()  # fills the example and message lines, then fits

    def _on_kind(self, event: wx.CommandEvent) -> None:
        """Show the own fields of the chosen kind; the shared fields stay as they are."""
        self._build(KINDS[self.kind.GetStringSelection()]())

    def calculation(self) -> Calculation:
        """Return the calculation as edited.

        Raises:
            ValueError: If a field is not valid (`FieldErrors` or a pydantic
                `ValidationError`, both subclasses of `ValueError`).
        """
        model = KINDS[self.kind.GetStringSelection()]
        values = self.shared.values(model())
        own = self.fields.values(model())
        values.update({name: own[name] for name in self.fields.editors})
        return model.model_validate(values)

    def validate(self) -> bool:
        """Validate the calculation and show the result.

        The problems are shown below the fields. A used, named calculation without
        problems shows its values for the first rows of the first non-empty input
        table, next to the columns it uses (`calculation_example`). OK is enabled
        only without errors.

        Returns:
            True if there are no errors.
        """
        from flim.core.calculate import validate_calculations
        from flim.core.tool import EXAMPLE_ROWS
        from flim.tools.data import calculation_example

        ok = self.FindWindowById(wx.ID_OK)
        self._show_preview()
        try:
            calculation = self.calculation()
        except (FieldErrors, ValidationError, ValueError) as err:
            text = "; ".join(err.errors.values()) if isinstance(err, FieldErrors) else str(err)
            self._show(None, text, ok, False)
            return False
        problems = [p for p in validate_calculations([calculation], self.columns) if p[0] == 0]
        # a column the table doesn't have: the calculation can't be made on it
        errors = [
            m for _, _, severity, m in problems
            if severity == "error" or m.startswith("skipped")
        ]  # fmt: skip
        warnings = [m for _, _, severity, m in problems if m not in errors]
        example = None
        table = next((t for t in self.tables if isinstance(t, pd.DataFrame) and len(t)), None)
        if not calculation.enabled:
            warnings.append("Not used: Use is unchecked")
        elif table is not None and calculation.name and not errors and not warnings:
            # as kept, so that a helper column shows its example too
            shown = calculation.model_copy(update={"keep": True})
            try:
                example = calculation_example([shown], table.head(EXAMPLE_ROWS), 1)
            except (ValueError, KeyError, TypeError) as err:
                errors.append(f"{calculation.name}: {err}")
        self._show(example, "\n".join(errors + warnings), ok, not errors)
        return not errors

    def _show_preview(self) -> None:
        """Show a function's call and its parameters and summary; hide it otherwise.

        For example `FAD tm = tm(FAD a1[%], FAD t1, FAD a2[%], FAD t2)` and
        `tm(a1perc, t1, a2perc, t2): Return the mean lifetime of two components, ...`.
        """
        lines = []
        if self.kind.GetStringSelection() == "function":
            try:
                calculation = self.calculation()
            except (FieldErrors, ValidationError, ValueError):
                calculation = None
            if calculation is not None and calculation.function:
                lines.append(f"{calculation.name or '?'} = {describe(calculation)}")
                lines.append(function_summary(calculation.function))
        self.preview.SetLabel("\n".join(line for line in lines if line))
        self.preview.Wrap(460)
        self.preview.Show(bool(lines))

    def _show(
        self, example: Any, message: str, ok: Optional[wx.Window], enabled: bool
    ) -> None:
        """Show the example (a table, a line or None) and the message; enable OK."""
        self.example.show(example)
        self.message.SetLabel(message)
        self.message.Wrap(460)
        if ok is not None:
            ok.Enable(enabled)
        self._fit()

    def _fit(self) -> None:
        """Grow the dialog to its content (e.g. a longer message); never shrink it."""
        self.Layout()
        needed = self.GetSizer().GetMinSize()
        client = self.GetClientSize()
        if needed.width > client.width or needed.height > client.height:
            self.SetClientSize(max(needed.width, client.width), max(needed.height, client.height))
            self.Layout()


def edit_calculation(
    parent: Optional[wx.Window],
    calculation: Optional[Calculation] = None,
    columns: Iterable[Any] = (),
    schema: Optional[TableSchema] = None,
    tables: Iterable[Any] = (),
) -> Optional[Calculation]:
    """Show the calculation editor as a modal dialog.

    Args:
        parent: The parent window.
        calculation: The calculation to edit. Defaults to None: a new expression.
        columns: The columns the calculation can use. Defaults to none.
        schema: The input's schema. Defaults to None.
        tables: The input tables. Defaults to none.

    Returns:
        The edited calculation, or None if the dialog was cancelled.
    """
    with CalculationDialog(parent, calculation, columns, schema, tables) as dialog:
        if dialog.ShowModal() != wx.ID_OK:
            return None
        return dialog.calculation()


# --- the read-only table ---


@register_editor(CalculateConfig, "calculations")
class CalculationsEditor(_RowIssues, Editor):
    """The calculations as a read-only table; each is edited in the calculation editor.

    The buttons add, edit, remove and move calculations, and load, save and remove
    presets. A double click on a row edits it.
    """

    expands = True
    HEADERS = ("New Column", "Calculation", "Options")

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the table and its buttons."""
        self.items: list = []
        self.schema = None
        self.tables: list = []
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.grid = wx.grid.Grid(panel)
        self.grid.CreateGrid(0, len(self.HEADERS))
        for i, header in enumerate(self.HEADERS):
            self.grid.SetColLabelValue(i, header)
        self.grid.EnableEditing(False)
        self.grid.SetRowLabelSize(30)
        self.grid.SetMinSize((-1, 130))
        self.grid.SetSelectionMode(wx.grid.Grid.GridSelectRows)
        self.grid.SetColAttr(0, self._init_row_issues())  # issue markers in column 1
        self.grid.GetGridWindow().Bind(wx.EVT_MOTION, self._on_motion)
        self.grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, lambda e: self._on_edit(e))
        sizer.Add(self.grid, 1, wx.EXPAND)
        for labels in (
            [("Add Calculation...", self._on_add), ("Edit...", self._on_edit),
             ("Remove", self._on_remove), ("Up", lambda e: self._move(-1)),
             ("Down", lambda e: self._move(1))],
            [("Load Preset...", self._on_load_presets), ("Save as Preset...", self._on_save_presets),
             ("Remove Presets...", self._on_remove_presets)],
        ):  # fmt: skip
            buttons = wx.BoxSizer(wx.HORIZONTAL)
            for label, handler in labels:
                button = wx.Button(panel, label=label, style=wx.BU_EXACTFIT)
                button.Bind(wx.EVT_BUTTON, handler)
                buttons.Add(button, 0, wx.TOP | wx.RIGHT, 3)
            sizer.Add(buttons)
        panel.SetSizer(sizer)
        return panel

    # --- the table ---

    def _show(self, select: Optional[int] = None) -> None:
        """Show the calculations in the table; select the row `select`."""
        if self.grid.GetNumberRows():
            self.grid.DeleteRows(0, self.grid.GetNumberRows())
        self.grid.AppendRows(len(self.items))
        for row, c in enumerate(self.items):
            options = [o for o, on in (("not used", not c.enabled), ("helper", not c.keep)) if on]
            for col, text in enumerate((c.name, describe(c), ", ".join(options))):
                self.grid.SetCellValue(row, col, text)
        self.grid.AutoSizeColumns()
        if select is not None and 0 <= select < len(self.items):
            self.grid.SelectRow(select)
            self.grid.SetGridCursor(select, 0)

    def _selected(self) -> list[int]:
        """Return the selected rows and the cursor's row, sorted."""
        rows = set(self.grid.GetSelectedRows()) | {self.grid.GetGridCursorRow()}
        return sorted(r for r in rows if 0 <= r < len(self.items))

    def _columns_before(self, row: int) -> list[Any]:
        """Return the input's columns and those of the calculations above `row`."""
        names = [] if self.schema is None else self.schema.names
        return names + [c.name for c in self.items[:row]]

    def _on_add(self, event: wx.CommandEvent) -> None:
        """Add a calculation edited in the calculation editor."""
        new = edit_calculation(
            self.control, None, self._columns_before(len(self.items)), self.schema, self.tables
        )
        if new is not None:
            self.items.append(new)
            self._show(len(self.items) - 1)
            self.changed()

    def _on_edit(self, event: wx.Event) -> None:
        """Edit the first selected calculation in the calculation editor."""
        rows = self._selected()
        if not rows:
            return
        row = rows[0]
        edited = edit_calculation(
            self.control, self.items[row], self._columns_before(row), self.schema, self.tables
        )
        if edited is not None:
            self.items[row] = edited
            self._show(row)
            self.changed()

    def _on_remove(self, event: wx.CommandEvent) -> None:
        """Remove the selected calculations."""
        for row in reversed(self._selected()):
            del self.items[row]
        self._show()
        self.changed()

    def _move(self, step: int) -> None:
        """Move the selected calculation by `step` rows, if one row is selected."""
        rows = self._selected()
        if len(rows) != 1:
            return
        row, other = rows[0], rows[0] + step
        if 0 <= other < len(self.items):
            self.items[row], self.items[other] = self.items[other], self.items[row]
            self._show(other)
            self.changed()

    # --- presets ---

    def _on_load_presets(self, event: wx.CommandEvent) -> None:
        """Add chosen presets that apply to the table, with their prerequisites."""
        from flim.core.calculate import applicable, with_prerequisites

        columns = self._columns_before(len(self.items))
        saved = saved_presets()
        offered = applicable(saved + built_in_presets(), columns)
        if not offered:
            wx.MessageBox(
                "No preset applies to this table: their columns are missing, or the"
                " table has their results already.",
                "Load Preset",
                wx.OK,
            )
            return
        saved_names = {p.name for p in saved}
        labels = [
            f"{p.name} = {describe(p)}" + ("  (saved)" if p.name in saved_names else "")
            for p in offered
        ]
        with wx.MultiChoiceDialog(
            self.control, "Calculations that apply to the table:", "Load Preset", labels
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            chosen = [offered[i] for i in dialog.GetSelections()]
        self.items += with_prerequisites(chosen, offered, columns)
        self._show()
        self.changed()

    def _on_save_presets(self, event: wx.CommandEvent) -> None:
        """Save the selected calculations as presets; same names are replaced."""
        new = [self.items[r] for r in self._selected()]
        if not new:
            wx.MessageBox("Select the calculations to save.", "Save as Preset", wx.OK)
            return
        names = {p.name for p in new}
        save_presets([p for p in saved_presets() if p.name not in names] + new)
        wx.MessageBox(
            f"Saved {len(new)} calculation(s); Load Preset... offers them.",
            "Save as Preset",
            wx.OK,
        )

    def _on_remove_presets(self, event: wx.CommandEvent) -> None:
        """Ask for saved presets and remove them."""
        saved = saved_presets()
        if not saved:
            wx.MessageBox(
                "There are no saved calculations (built-in ones can't be removed).",
                "Remove Presets",
                wx.OK,
            )
            return
        with wx.MultiChoiceDialog(
            self.control, "Saved calculations to remove:", "Remove Presets",
            [f"{p.name} = {describe(p)}" for p in saved],
        ) as dialog:  # fmt: skip
            if dialog.ShowModal() != wx.ID_OK:
                return
            removed = set(dialog.GetSelections())
        save_presets([p for i, p in enumerate(saved) if i not in removed])

    # --- Editor ---

    def _row_of(self, path: Optional[str]) -> Optional[int]:
        """Return the row of an issue's path, e.g. `calculations[2].name`; else None."""
        rest = (path or "")[len(self.spec.name):].lstrip(".")
        number = rest.removeprefix("[").split("]")[0]
        return int(number) if number.isdigit() else None

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Store the input's schema for the calculation editor."""
        self.schema = schema

    def set_data(self, tables: list) -> None:
        """Store the input tables for the calculation editor's example."""
        self.tables = list(tables)

    def get(self) -> Any:
        """Return the calculations as dicts."""
        return [c.model_dump(mode="json") for c in self.items]

    def set(self, value: Any) -> None:
        """Show calculations (configs or dicts; None for none) in the table."""
        self.items = list(CalculateConfig(calculations=list(value or [])).calculations)
        self._show()

