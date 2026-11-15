"""Editors of the readers' dialogs: the workflow Import Tables runs."""

from pathlib import Path
from typing import Any, Optional

import wx

from flim.configs.data import ImportTablesConfig
from flim.gui.editors import Editor, register_editor

NONE = "None (open the tables)"
OTHER = "Other Workflow File..."


@register_editor(ImportTablesConfig, "workflow")
class WorkflowEditor(Editor):
    """Choice of the workflow run on the imported tables.

    The choices are none, the workflows tagged `import` (see
    `flim.core.workflowfile.import_workflows`), and `Other Workflow File...`, which
    asks for a workflow file and adds it to the choices.
    """

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the drop-down; it selects none."""
        from flim.core.workflowfile import import_workflows

        self.values = [None] + [t.name for t in import_workflows()]
        control = wx.Choice(parent, choices=self._labels())
        control.SetSelection(0)
        control.Bind(wx.EVT_CHOICE, self._on_choice)
        self._previous = 0
        return control

    def _labels(self) -> list[str]:
        """Return the labels of the drop-down: none, the workflows, other file."""
        return [NONE] + [str(v) for v in self.values[1:]] + [OTHER]

    def _on_choice(self, event: wx.CommandEvent) -> None:
        """Handle a selection; `Other Workflow File...` asks for a file."""
        index = self.control.GetSelection()
        if index == len(self.values):  # Other Workflow File...
            path = self._ask_file()
            if path is None:
                self.control.SetSelection(self._previous)
                return
            self.set(path)
        self._previous = self.control.GetSelection()
        self.changed(event)

    def _ask_file(self) -> Optional[str]:
        """Ask for a workflow file and check it; None if cancelled or it has errors."""
        from flim.core.workflowfile import check_workflow_file

        with wx.FileDialog(
            self.control, "Workflow file", wildcard="Workflow files (*.json)|*.json|All files|*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:  # fmt: skip
            if dialog.ShowModal() != wx.ID_OK:
                return None
            path = dialog.GetPath()
        check = check_workflow_file(path)
        if check.errors:
            wx.MessageBox("\n".join(check.errors), "Workflow file", wx.OK | wx.ICON_ERROR)
            return None
        return path

    def get(self) -> Any:
        """Return the selected workflow's name or file path; None for none."""
        index = self.control.GetSelection()
        return self.values[index] if 0 <= index < len(self.values) else None

    def set(self, value: Any) -> None:
        """Select a workflow by name or file path; None or empty selects none.

        A file path that is not among the choices is added. A name that is not
        among the choices and not a `.json` path leaves the selection unchanged.
        """
        if value and value not in self.values:
            if not Path(str(value)).suffix.lower() == ".json":
                return  # a workflow no longer registered: selection unchanged
            self.values.append(str(value))
            self.control.Set(self._labels())
        self.control.SetSelection(self.values.index(value) if value else 0)
        self._previous = self.control.GetSelection()
