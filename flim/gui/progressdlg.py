"""Dialogs shown while a tool or workflow runs and after it was cancelled."""

import gc
import logging
import os
import subprocess
import sys
import threading

import wx
import wx.adv

from flim.core.runner import FINAL_STATUSES, CancelToken


def open_in_file_browser(path):
    """Shows a folder in Finder, Explorer or the Linux file manager (creating it
    if it does not exist yet)."""
    os.makedirs(path, exist_ok=True)
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path])


class FolderLink(wx.adv.HyperlinkCtrl):
    """Shows a folder path; clicking it opens the folder in the file browser."""

    def __init__(self, parent, path=""):
        super().__init__(parent, wx.ID_ANY, path or " ", "")
        self.path = path
        self.SetToolTip("Open in the file browser")
        self.Bind(wx.adv.EVT_HYPERLINK, self.OnClick)

    def SetPath(self, path):
        self.path = path
        self.SetLabel(path)

    def OnClick(self, event):
        # instead of opening a URL in the web browser
        if self.path:
            open_in_file_browser(self.path)


class RunProgressDialog(wx.Dialog):
    """Modal progress dialog that runs a flow in a worker thread.

    While the dialog is shown the rest of the application is blocked, but the event
    loop keeps running. Cancel (or closing the window) cancels the run; the dialog
    closes itself when the run has ended.

    Args:
        parent: parent window.
        title: name of the tool or workflow.
        start_run: callable ``start_run(cancel_token, on_progress, on_start)`` that
            runs the flow (in the worker thread), passing the three on to
            :func:`~flim.core.runner.run_flow`, and returns the
            :class:`~flim.core.runner.FlowRun`.

    After :meth:`ShowModal` (``wx.ID_OK`` or ``wx.ID_CANCEL`` if cancelled),
    :attr:`run` holds the FlowRun, or :attr:`error` the exception that stopped it.
    """

    def __init__(self, parent, title, start_run):
        super().__init__(parent, wx.ID_ANY, title=title)
        self.start_run = start_run
        self.cancel_token = CancelToken()
        self.run = None
        self.error = None
        self._flow_run = None  # the FlowRun, once Prefect has created it

        self.task_text = wx.StaticText(self, label="Starting...")
        self.gauge = wx.Gauge(self, range=1, size=(420, -1))
        self.count_text = wx.StaticText(self, label="")
        # link to the flow run, shown once known if a Prefect server is used
        self.link_text = wx.StaticText(self, label="Flow run on the Prefect server:")
        self.link = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, " ", "")
        self.link_text.Hide()
        self.link.Hide()
        # results folder, shown once known if results are saved
        self.folder_text = wx.StaticText(self, label="Results are saved in:")
        self.folder = FolderLink(self)
        self.folder_text.Hide()
        self.folder.Hide()
        # expandable list of all tasks and their status
        self.tasks_pane = wx.CollapsiblePane(self, label="Tasks")
        pane = self.tasks_pane.GetPane()
        self.task_list = wx.ListCtrl(pane, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(420, 200))
        self.task_list.AppendColumn("Task", width=300)
        self.task_list.AppendColumn("Status", width=100)
        pane_sizer = wx.BoxSizer(wx.VERTICAL)
        pane_sizer.Add(self.task_list, 1, wx.EXPAND)
        pane.SetSizer(pane_sizer)
        self.tasks_pane.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, lambda event: self.Fit())
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)
        self.Bind(wx.EVT_CLOSE, self.OnCancel)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.task_text, 0, wx.ALL | wx.EXPAND, 10)
        sizer.Add(self.gauge, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        sizer.Add(self.count_text, 0, wx.ALL | wx.EXPAND, 10)
        sizer.Add(self.link_text, 0, wx.LEFT | wx.RIGHT, 10)
        sizer.Add(self.link, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        sizer.Add(self.folder_text, 0, wx.LEFT | wx.RIGHT, 10)
        sizer.Add(self.folder, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        sizer.Add(self.tasks_pane, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        sizer.Add(self.cancel_button, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizerAndFit(sizer)

        # status, count, bar and task list are refreshed together from the task
        # statuses: on every progress event and regularly (the bar pulses until
        # the number of tasks is known)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda event: self._refresh(), self.timer)
        self.timer.Start(200)
        # start once the modal loop is running, so that a quick run can end it
        wx.CallAfter(self._start)

    def _start(self):
        # Python's cyclic garbage collector runs in whichever thread allocates when
        # it triggers; if it frees wx objects in a worker thread, the app crashes.
        # While the flow runs, collect only here, on the main thread.
        gc.collect()
        self._gc_was_enabled = gc.isenabled()
        gc.disable()
        self._gc_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda event: gc.collect(), self._gc_timer)
        self._gc_timer.Start(1000)
        threading.Thread(target=self._work, name="flow-run", daemon=True).start()

    def _restore_gc(self):
        timer = getattr(self, "_gc_timer", None)
        if timer is not None:
            timer.Stop()
            self._gc_timer = None
            if self._gc_was_enabled:
                gc.enable()
            gc.collect()

    def _work(self):
        try:
            self.run = self.start_run(self.cancel_token, self._on_progress, self._on_start)
        except Exception as e:
            logging.exception("Run failed")
            self.error = e
        wx.CallAfter(self._finished)

    def _on_start(self, run):
        wx.CallAfter(self._started, run)

    def _started(self, run):
        if not self:  # destroyed before the update arrived
            return
        self._flow_run = run
        url = run.ui_url
        if url:
            self.link.SetLabel(url)
            self.link.SetURL(url)
            self.link_text.Show()
            self.link.Show()
        if run.autosave_dir:
            self.folder.SetPath(run.autosave_dir)
            self.folder_text.Show()
            self.folder.Show()
        self.Fit()

    def _on_progress(self, done, total, label, complete):
        wx.CallAfter(self._refresh)

    @staticmethod
    def _names(labels, shown=3):
        names = ", ".join(labels[:shown])
        return names + (f" and {len(labels) - shown} more" if len(labels) > shown else "")

    def _refresh(self):
        """Shows the current task statuses: status line, count, bar and list."""
        if not self:  # destroyed before the update arrived
            return
        if self._flow_run is None:
            self.gauge.Pulse()
            return
        tasks = self._flow_run.tasks()
        for row, (label, status) in enumerate(tasks):
            if row >= self.task_list.GetItemCount():
                self.task_list.Append([label, status])
            elif self.task_list.GetItemText(row, 1) != status:
                self.task_list.SetItem(row, 1, status)

        running = [label for label, status in tasks if status == "running"]
        pending = sum(status == "pending" for _, status in tasks)
        done = sum(status in FINAL_STATUSES for _, status in tasks)
        if self.cancel_token.is_set():
            what = self._names(running) if running else "the running tasks"
            status_line = f"Cancelling, waiting for {what} to finish..."
        elif running:
            status_line = f"Running: {self._names(running)}"
        elif pending:
            status_line = f"Waiting for {pending} task{'s' if pending > 1 else ''} to start..."
        else:
            status_line = "Starting..." if not tasks else "Finishing..."
        self.task_text.SetLabel(status_line)
        if self._flow_run.complete:
            self.gauge.SetRange(max(len(tasks), 1))
            self.gauge.SetValue(done)
            self.count_text.SetLabel(f"{done} of {len(tasks)} tasks completed")
        else:
            self.gauge.Pulse()
            self.count_text.SetLabel(f"{done} of {len(tasks)} tasks completed so far")
        self.Layout()

    def OnCancel(self, event):
        if self.cancel_token.is_set():
            return
        self.cancel_token.set()
        self.cancel_button.Disable()
        self._refresh()

    def _finished(self):
        if not self:
            return
        self._restore_gc()
        self.timer.Stop()
        self._refresh()
        self.EndModal(wx.ID_CANCEL if self.cancel_token.is_set() else wx.ID_OK)


class RunSummaryDialog(wx.Dialog):
    """Says how a run ended and links to its results folder and Prefect flow run.

    Shown after every workflow run and after a cancelled tool run.

    Args:
        parent: parent window.
        title: name of the tool or workflow.
        run (flim.core.runner.FlowRun): the finished run.
    """

    def __init__(self, parent, title, run):
        super().__init__(parent, wx.ID_ANY, title=title)
        counts = run.task_counts()
        total = sum(counts.values())
        completed = counts.get("completed", 0)
        sizer = wx.BoxSizer(wx.VERTICAL)

        def text(label):
            sizer.Add(wx.StaticText(self, label=label), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        if run.state == "cancelled":
            text(f"{title} was cancelled after {completed} of {total} tasks.")
            folder_label = "Results of the completed tasks are in:"
        elif run.failed:
            failed = run.failed
            names = ", ".join(failed[:5]) + (f" and {len(failed) - 5} more" if len(failed) > 5 else "")
            text(
                f"{title} finished: {completed} of {total} tasks completed,"
                f" {len(failed)} failed: {names}"
            )
            text("See the log for details.")
            folder_label = "Results of the completed tasks are in:"
        else:
            text(f"{title} completed all {total} tasks.")
            folder_label = "Results are in:"
        self.results_dir = run.autosave_dir
        self.folder = None
        if self.results_dir:
            text(folder_label)
            self.folder = FolderLink(self, self.results_dir)
            sizer.Add(self.folder, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        else:
            text("No results were saved because Autosave is off.")
        self.link = None
        if run.ui_url:
            text("Flow run on the Prefect server:")
            self.link = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, run.ui_url, run.ui_url)
            sizer.Add(self.link, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        sizer.Add(self.CreateButtonSizer(wx.OK), 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizerAndFit(sizer)
