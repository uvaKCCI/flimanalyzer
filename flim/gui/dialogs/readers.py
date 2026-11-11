"""Editors of the readers' dialogs: the workflow Import Tables runs."""

from pathlib import Path

import wx

from flim.configs.data import ImportTablesConfig
from flim.gui.editors import Editor, register_editor

NONE = "None (open the tables)"
OTHER = "Other Workflow File..."


@register_editor(ImportTablesConfig, "workflow")
class WorkflowEditor(Editor):
    """The workflow run on the tables: none, a workflow tagged `import` (see
    `flim.core.workflowfile.import_workflows`), or another workflow file."""

    def create(self, parent):
        from flim.core.workflowfile import import_workflows

        self.values = [None] + [t.name for t in import_workflows()]
        control = wx.Choice(parent, choices=self._labels())
        control.SetSelection(0)
        control.Bind(wx.EVT_CHOICE, self._on_choice)
        self._previous = 0
        return control

    def _labels(self) -> list:
        return [NONE] + [str(v) for v in self.values[1:]] + [OTHER]

    def _on_choice(self, event):
        index = self.control.GetSelection()
        if index == len(self.values):  # Other Workflow File...
            path = self._ask_file()
            if path is None:
                self.control.SetSelection(self._previous)
                return
            self.set(path)
        self._previous = self.control.GetSelection()
        self.changed(event)

    def _ask_file(self):
        """Ask for a workflow file and check it; None if none is chosen or it has
        errors (they are shown)."""
        from flim.core.workflowfile import check_workflow_file

        with wx.FileDialog(
            self.control, "Workflow file", wildcard="Workflow files (*.json)|*.json",
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

    def get(self):
        index = self.control.GetSelection()
        return self.values[index] if 0 <= index < len(self.values) else None

    def set(self, value):
        if value and value not in self.values:
            if not Path(str(value)).suffix.lower() == ".json":
                return  # a workflow that is no longer registered: None
            self.values.append(str(value))
            self.control.Set(self._labels())
        self.control.SetSelection(self.values.index(value) if value else 0)
        self._previous = self.control.GetSelection()
