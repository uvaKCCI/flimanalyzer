"""Dialogs shown while a tool or workflow runs and after it was cancelled."""

import contextvars
import gc
import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable
from typing import Optional

import wx
import wx.adv

from flim.core.paths import shorten_path
from flim.core.runner import FINAL_STATUSES, CancelToken, FlowRun

logger = logging.getLogger(__name__)

# called as `on_progress(done, total, label, complete)`
ProgressCallback = Callable[[int, int, str, bool], None]


def open_in_file_browser(path: str | os.PathLike) -> None:
    """Show a folder in the file browser; create the folder if it does not exist.

    The folder opens in Finder (macOS), Explorer (Windows) or, elsewhere, with
    `xdg-open`.

    Args:
        path: The folder.
    """
    os.makedirs(path, exist_ok=True)
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path])


class FolderLink(wx.adv.HyperlinkCtrl):
    """Shows a folder path; clicking it opens the folder in the file browser."""

    def __init__(self, parent: wx.Window, path: str | os.PathLike = "") -> None:
        """Create the link.

        Args:
            parent: The parent window.
            path: The folder; an empty string shows no path. Defaults to "".
        """
        super().__init__(parent, wx.ID_ANY, " ", "")
        self.Bind(wx.adv.EVT_HYPERLINK, self.OnClick)
        self.SetPath(path)

    def SetPath(self, path: str | os.PathLike) -> None:
        """Show `path` (long paths shortened); the tooltip has the whole path."""
        self.path = path
        self.SetLabel(shorten_path(path) if path else " ")
        self.SetToolTip(f"{path}\nOpen in the file browser" if path else "")

    def OnClick(self, event: wx.adv.HyperlinkEvent) -> None:
        """Open the folder in the file browser."""
        # instead of opening a URL in the web browser
        if self.path:
            open_in_file_browser(self.path)


class RunProgressDialog(wx.Dialog):
    """Modal progress dialog that runs a flow in a worker thread.

    While the dialog is shown the rest of the GUI is blocked, but the event
    loop keeps running. Cancel (or closing the window) cancels the run; the dialog
    closes itself when the run has ended.

    After `ShowModal` (`wx.ID_OK`, or `wx.ID_CANCEL` if cancelled), `run` holds the
    `FlowRun`, or `error` the exception that stopped it.
    """

    def __init__(
        self,
        parent: Optional[wx.Window],
        title: str,
        start_run: Callable[
            [CancelToken, ProgressCallback, Callable[[FlowRun], None]], FlowRun
        ],
    ) -> None:
        """Create the dialog; the run starts once the modal loop is running.

        Args:
            parent: The parent window.
            title: The name of the tool or workflow.
            start_run: Called as `start_run(cancel_token, on_progress, on_start)` in
                the worker thread; runs the flow, passing the three on to
                `flim.core.runner.run_flow`, and returns the `FlowRun`.
        """
        super().__init__(parent, wx.ID_ANY, title=title)
        self.start_run = start_run
        self.cancel_token = CancelToken()
        self.run = None
        self.error = None
        self._flow_run = None  # the FlowRun, once the flow has started

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

    def _start(self) -> None:
        """Start the run in a worker thread, with garbage collection on this thread."""
        # Python's cyclic garbage collector runs in whichever thread allocates when
        # it triggers; if it frees wx objects in a worker thread, the process can
        # crash.
        # While the flow runs, collect only here, on the main thread.
        gc.collect()
        self._gc_was_enabled = gc.isenabled()
        gc.disable()
        self._gc_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda event: gc.collect(), self._gc_timer)
        self._gc_timer.Start(1000)
        # in a copy of this thread's context: the flow uses the Prefect server chosen
        # at startup (use_prefect_server), not the settings Prefect read at import
        context = contextvars.copy_context()
        threading.Thread(
            target=context.run, args=(self._work,), name="flow-run", daemon=True
        ).start()

    def _restore_gc(self) -> None:
        """Stop the collection timer and restore automatic garbage collection."""
        timer = getattr(self, "_gc_timer", None)
        if timer is not None:
            timer.Stop()
            self._gc_timer = None
            if self._gc_was_enabled:
                gc.enable()
            gc.collect()

    def _work(self) -> None:
        """Run the flow in the worker thread and store its run or error."""
        from flim.core.prefect_server import checked_prefect_server

        try:
            with checked_prefect_server():
                self.run = self.start_run(
                    self.cancel_token, self._on_progress, self._on_start
                )
        except Exception as e:
            logger.exception("Run failed")
            self.error = e
        wx.CallAfter(self._finished)

    @property
    def started_run(self) -> Optional[FlowRun]:
        """Return the run once Prefect has started it, also if it failed later; else None."""
        return self._flow_run

    def _on_start(self, run: FlowRun) -> None:
        """Pass the started run to the main thread."""
        wx.CallAfter(self._started, run)

    def _started(self, run: FlowRun) -> None:
        """Show the links to the run on the Prefect server and to its results."""
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

    def _on_progress(self, done: int, total: int, label: str, complete: bool) -> None:
        """Refresh the dialog on the main thread."""
        wx.CallAfter(self._refresh)

    @staticmethod
    def _names(labels: list[str], shown: int = 3) -> str:
        """Return the first `shown` labels and the number of the others."""
        names = ", ".join(labels[:shown])
        return names + (f" and {len(labels) - shown} more" if len(labels) > shown else "")

    def _refresh(self) -> None:
        """Show the current task statuses: status line, count, bar and list."""
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

    def OnCancel(self, event: wx.Event) -> None:
        """Cancel the run; the dialog closes when the run has ended."""
        if self.cancel_token.is_set():
            return
        self.cancel_token.set()
        self.cancel_button.Disable()
        self._refresh()

    def _finished(self) -> None:
        """Restore the garbage collection, show the final statuses and close."""
        if not self:
            return
        self._restore_gc()
        self.timer.Stop()
        self._refresh()
        self._end_modal()

    def _end_modal(self) -> None:
        """End the modal loop, and check again later until it has ended."""
        if not self or not self.IsModal():
            return
        self.EndModal(wx.ID_CANCEL if self.cancel_token.is_set() else wx.ID_OK)
        # a run that ends at once can call EndModal before the modal loop really runs;
        # macOS then ignores it and ShowModal never returns: check again
        wx.CallLater(200, self._end_modal)


class RunSummaryDialog(wx.Dialog):
    """Shows how a run ended, with links to its results and its Prefect flow run.

    The dialog lists the numbers of completed and failed tasks, the names of up to
    five failed tasks and up to five warnings, and links to the results folder and
    to the flow run on the Prefect server, if there are any.
    """

    def __init__(self, parent: Optional[wx.Window], title: str, run: FlowRun) -> None:
        """Create the dialog.

        Args:
            parent: The parent window.
            title: The name of the tool or workflow.
            run: The finished run.
        """
        super().__init__(parent, wx.ID_ANY, title=title)
        counts = run.task_counts()
        total = sum(counts.values())
        completed = counts.get("completed", 0)
        sizer = wx.BoxSizer(wx.VERTICAL)

        def text(label: str) -> None:
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
        warnings = getattr(run, "warnings", [])
        if warnings:
            shown = "\n".join(f"{label}: {message}" for label, message in warnings[:5])
            more = f"\n... and {len(warnings) - 5} more" if len(warnings) > 5 else ""
            text(f"Warnings:\n{shown}{more}")
        self.results_dir = run.autosave_dir
        self.folder = None
        if self.results_dir:
            text(folder_label)
            self.folder = FolderLink(self, self.results_dir)
            sizer.Add(self.folder, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        else:
            text("No results were saved because Save results is off.")
        self.link = None
        if run.ui_url:
            text("Flow run on the Prefect server:")
            self.link = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, run.ui_url, run.ui_url)
            sizer.Add(self.link, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        sizer.Add(self.CreateButtonSizer(wx.OK), 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizerAndFit(sizer)
