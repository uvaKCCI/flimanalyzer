"""Calculate: the calculations as a read-only table, edited one at a time.

The table starts empty (Calculate.dialog_config). `Add Calculation...` and `Edit...`
open the calculation editor: a kind (expression or function), then only that kind's
fields, generated from its config; the function's parameters are generated from its
signature. `Load Presets...` adds presets that apply to the input table: the
built-in calculations and those saved with `Save as Presets` (the user settings'
`calculation_presets`). `Remove Presets...` removes saved ones; the built-in ones
can't be removed.
"""

import inspect
import logging
from typing import Optional

import pandas as pd
import wx
import wx.grid
from pydantic import ValidationError, create_model

from flim.configs.data import CalculateConfig, ExpressionCalculation, FunctionCalculation
from flim.gui.editors import (
    CategoriesEditor,
    Editor,
    FieldErrors,
    FieldsPanel,
    _RowIssues,
    register_editor,
)

logger = logging.getLogger(__name__)

KINDS = {"expression": ExpressionCalculation, "function": FunctionCalculation}
_settings_manager = None  # the session's SettingsManager (see bind)


def bind(settings_manager) -> None:
    """Use a session's settings for the saved presets.

    Args:
        settings_manager: The SettingsManager of the session.
    """
    global _settings_manager
    _settings_manager = settings_manager


def built_in_presets() -> list:
    """The built-in calculations: those of the import (FLIRR, NAD(P)H tm, ...)."""
    return list(CalculateConfig().calculations)


def saved_presets() -> list:
    """The calculations saved as presets; those that are not valid are left out."""
    if _settings_manager is None:
        return []
    presets = []
    for data in _settings_manager.settings.calculation_presets:
        try:
            presets.extend(CalculateConfig(calculations=[data]).calculations)
        except ValueError as err:
            logger.warning(f"Saved calculation not valid, not offered: {err}")
    return presets


def save_presets(presets) -> None:
    """Replace the saved presets (written to the user settings file)."""
    if _settings_manager is not None:
        _settings_manager.update(
            {"calculation_presets": [p.model_dump(mode="json") for p in presets]}
        )


def describe(calculation) -> str:
    """What a calculation computes, e.g. `ratio(NAD(P)H a2[%], FAD a1[%])`."""
    if calculation.kind == "expression":
        return calculation.expression
    params = ", ".join(f"{k}={v:g}" for k, v in calculation.params.items())
    args = ", ".join(map(str, calculation.args)) + (f"; {params}" if params else "")
    return f"{calculation.function}({args})"


# --- the editors of a function's fields ---


def _functions() -> list:
    from flim.core.calculate import FUNCTIONS, _register_builtins

    _register_builtins()
    return sorted(FUNCTIONS)


@register_editor(FunctionCalculation, "function")
class FunctionEditor(Editor):
    """The registered functions to choose from."""

    def create(self, parent):
        self.names = _functions()
        control = wx.Choice(parent, choices=self.names)
        control.Bind(wx.EVT_CHOICE, self.changed)
        return control

    def get(self):
        index = self.control.GetSelection()
        if index == wx.NOT_FOUND:
            raise ValueError("Choose a function")
        return self.names[index]

    def set(self, value):
        if value in self.names:
            self.control.SetSelection(self.names.index(value))


@register_editor(FunctionCalculation, "args")
class ArgumentsEditor(CategoriesEditor):
    """The function's argument columns: the input's features, checked and in order."""

    def set_schema(self, schema):
        self._remember()
        self.known = schema is not None and schema.complete
        self.columns = [] if schema is None else schema.by_role("feature")
        self._show()


def parameters_model(function: Optional[str]):
    """A config class with a field per keyword parameter of a registered function
    (those with defaults), e.g. `const` of `trp_Eperc_1`; None if it has none."""
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
    """The chosen function's parameters, one field each, with their defaults."""

    def create(self, parent):
        self.panel = wx.Panel(parent)
        self.panel.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.function = None
        self.fields = None  # the FieldsPanel of the function's parameters
        self.values: dict = {}
        self.none = wx.StaticText(self.panel, label="(none)")
        self.panel.GetSizer().Add(self.none)
        return self.panel

    def _rebuild(self, function) -> None:
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

    def refresh(self, panel):
        function = panel.value_of("function")
        if function != self.function:
            self._rebuild(function)
            panel.Layout()

    def get(self):
        if self.fields is None:
            return {}
        model = self.fields.model
        values = self.fields.values(model())
        return {k: v for k, v in values.items() if k in model.model_fields}

    def set(self, value):
        self.values = dict(value or {})
        self._rebuild(self.function)


# --- the calculation editor ---


class CalculationDialog(wx.Dialog):
    """Edits one calculation: its kind, then only the fields of that kind."""

    def __init__(self, parent, calculation=None, columns=(), schema=None, tables=()):
        """
        Args:
            parent: The parent window.
            calculation: The calculation to edit; None: a new expression.
            columns: The columns the calculation can use: the input's and those of
                the calculations before it.
            schema: The input's schema (column choices).
            tables: The input tables (the example line).
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
        self.body = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.body, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self.example = wx.StaticText(self, label="")
        self.message = wx.StaticText(self, label="")
        self.message.SetForegroundColour(wx.Colour(180, 0, 0))
        sizer.Add(self.example, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self.message, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        self.fields = None
        self._build(calculation)

    def _build(self, calculation) -> None:
        if self.fields is not None:
            self.fields.Destroy()
        self.fields = FieldsPanel(self, type(calculation), exclude={"kind", "engine"})
        self.fields.set_schema(self.schema)
        self.fields.set_data(self.tables)
        self.fields.set_values(calculation)
        self.fields.on_change = self.validate
        self.body.Add(self.fields, 1, wx.EXPAND)
        self.validate()  # fills the example and message lines, then fits

    def _on_kind(self, event):
        model = KINDS[self.kind.GetStringSelection()]
        name = self.fields.value_of("name") or ""
        self._build(model(name=name))

    def calculation(self):
        """Return the calculation as edited.

        Raises:
            ValueError: If a field is not valid (FieldErrors or a validation error).
        """
        model = KINDS[self.kind.GetStringSelection()]
        return model.model_validate(self.fields.values(model()))

    def validate(self) -> bool:
        """Check the calculation; show the problems and an example from the table's
        first row; enable OK only without errors."""
        from flim.core.calculate import calculate, check

        ok = self.FindWindowById(wx.ID_OK)
        try:
            calculation = self.calculation()
        except (FieldErrors, ValidationError, ValueError) as err:
            text = "; ".join(err.errors.values()) if isinstance(err, FieldErrors) else str(err)
            self._show("", text, ok, False)
            return False
        problems = [p for p in check([calculation], self.columns) if p[0] == 0]
        # a column the table doesn't have: the calculation can't be made on it
        errors = [
            m for _, _, severity, m in problems
            if severity == "error" or m.startswith("skipped")
        ]  # fmt: skip
        warnings = [m for _, _, severity, m in problems if m not in errors]
        example = ""
        table = next((t for t in self.tables if isinstance(t, pd.DataFrame) and len(t)), None)
        if not calculation.enabled:
            warnings.append("Not used: Use is unchecked")
        elif table is not None and calculation.name and not errors and not warnings:
            # as kept, so that a helper column shows its example too
            shown = calculation.model_copy(update={"keep": True})
            try:
                values = calculate(table.iloc[:1], [shown]).data
                value = values[calculation.name].iloc[0]
                text = f"{value:.4g}" if isinstance(value, float) else str(value)
                example = f"Example: {calculation.name} = {text}"
            except (ValueError, KeyError, TypeError) as err:
                errors.append(f"{calculation.name}: {err}")
        self._show(example, "\n".join(errors + warnings), ok, not errors)
        return not errors

    def _show(self, example, message, ok, enabled) -> None:
        self.example.SetLabel(example)
        self.message.SetLabel(message)
        self.message.Wrap(460)
        if ok is not None:
            ok.Enable(enabled)
        self._fit()

    def _fit(self) -> None:
        """Grow the dialog to its content (e.g. a longer message), never shrink it,
        so that no field is cut off."""
        self.Layout()
        needed = self.GetSizer().GetMinSize()
        client = self.GetClientSize()
        if needed.width > client.width or needed.height > client.height:
            self.SetClientSize(max(needed.width, client.width), max(needed.height, client.height))
            self.Layout()


def edit_calculation(parent, calculation=None, columns=(), schema=None, tables=()):
    """Show the calculation editor; return the calculation, or None if cancelled."""
    with CalculationDialog(parent, calculation, columns, schema, tables) as dialog:
        if dialog.ShowModal() != wx.ID_OK:
            return None
        return dialog.calculation()


# --- the read-only table ---


@register_editor(CalculateConfig, "calculations")
class CalculationsEditor(_RowIssues, Editor):
    """The calculations as a read-only table; each is edited in the calculation
    editor. The buttons add, edit, remove and move calculations, and load, save and
    remove presets."""

    expands = True
    HEADERS = ("New Column", "Calculation", "Options")

    def create(self, parent):
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
            [("Load Presets...", self._on_load_presets), ("Save as Presets", self._on_save_presets),
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

    def _selected(self) -> list:
        rows = set(self.grid.GetSelectedRows()) | {self.grid.GetGridCursorRow()}
        return sorted(r for r in rows if 0 <= r < len(self.items))

    def _columns_before(self, row: int) -> list:
        """The columns a calculation at `row` can use: the input's and those of the
        calculations above it."""
        names = [] if self.schema is None else self.schema.names
        return names + [c.name for c in self.items[:row]]

    def _on_add(self, event):
        new = edit_calculation(
            self.control, None, self._columns_before(len(self.items)), self.schema, self.tables
        )
        if new is not None:
            self.items.append(new)
            self._show(len(self.items) - 1)
            self.changed()

    def _on_edit(self, event):
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

    def _on_remove(self, event):
        for row in reversed(self._selected()):
            del self.items[row]
        self._show()
        self.changed()

    def _move(self, step: int) -> None:
        rows = self._selected()
        if len(rows) != 1:
            return
        row, other = rows[0], rows[0] + step
        if 0 <= other < len(self.items):
            self.items[row], self.items[other] = self.items[other], self.items[row]
            self._show(other)
            self.changed()

    # --- presets ---

    def _on_load_presets(self, event):
        from flim.core.calculate import applicable, with_prerequisites

        columns = self._columns_before(len(self.items))
        saved = saved_presets()
        offered = applicable(saved + built_in_presets(), columns)
        if not offered:
            wx.MessageBox(
                "No preset applies to this table: their columns are missing, or the"
                " table has their results already.",
                "Load Presets",
                wx.OK,
            )
            return
        saved_names = {p.name for p in saved}
        labels = [
            f"{p.name} = {describe(p)}" + ("  (saved)" if p.name in saved_names else "")
            for p in offered
        ]
        with wx.MultiChoiceDialog(
            self.control, "Calculations that apply to the table:", "Load Presets", labels
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            chosen = [offered[i] for i in dialog.GetSelections()]
        self.items += with_prerequisites(chosen, offered, columns)
        self._show()
        self.changed()

    def _on_save_presets(self, event):
        new = [self.items[r] for r in self._selected()]
        if not new:
            wx.MessageBox("Select the calculations to save.", "Save as Presets", wx.OK)
            return
        names = {p.name for p in new}
        save_presets([p for p in saved_presets() if p.name not in names] + new)
        wx.MessageBox(
            f"Saved {len(new)} calculation(s); Load Presets... offers them.",
            "Save as Presets",
            wx.OK,
        )

    def _on_remove_presets(self, event):
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

    def _row_of(self, path) -> Optional[int]:
        rest = (path or "")[len(self.spec.name):].lstrip(".")
        number = rest.removeprefix("[").split("]")[0]
        return int(number) if number.isdigit() else None

    def set_schema(self, schema):
        self.schema = schema

    def set_data(self, tables):
        self.tables = list(tables)

    def get(self):
        return [c.model_dump(mode="json") for c in self.items]

    def set(self, value):
        self.items = list(CalculateConfig(calculations=list(value or [])).calculations)
        self._show()

