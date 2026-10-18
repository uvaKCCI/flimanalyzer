"""Dialogs shown while a tool or workflow runs and after it was cancelled."""

import logging
import threading

import wx
import wx.adv

from flim.core.runner import CancelToken


class RunProgressDialog(wx.Dialog):
    """Modal progress dialog that runs a flow in a worker thread.

    While the dialog is shown the rest of the application is blocked, but the event
    loop keeps running. Cancel (or closing the window) cancels the run; the dialog
    closes itself when the run has ended.

    Args:
        parent: parent window.
        title: name of the tool or workflow.
        start_run: callable ``start_run(cancel_token, on_progress)`` that runs the
            flow (in the worker thread) and returns the
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
        self._current = ""
        self._complete = False

        self.task_text = wx.StaticText(self, label="Starting...")
        self.gauge = wx.Gauge(self, range=1, size=(360, -1))
        self.count_text = wx.StaticText(self, label="")
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)
        self.Bind(wx.EVT_CLOSE, self.OnCancel)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.task_text, 0, wx.ALL | wx.EXPAND, 10)
        sizer.Add(self.gauge, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        sizer.Add(self.count_text, 0, wx.ALL | wx.EXPAND, 10)
        sizer.Add(self.cancel_button, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizerAndFit(sizer)

        # the gauge pulses until the number of tasks is known
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda event: self.gauge.Pulse(), self.timer)
        self.timer.Start(100)
        # start once the modal loop is running, so that a quick run can end it
        wx.CallAfter(self._start)

    def _start(self):
        threading.Thread(target=self._work, name="flow-run", daemon=True).start()

    def _work(self):
        try:
            self.run = self.start_run(self.cancel_token, self._on_progress)
        except Exception as e:
            logging.exception("Run failed")
            self.error = e
        wx.CallAfter(self._finished)

    def _on_progress(self, done, total, label, complete):
        wx.CallAfter(self._update, done, total, label, complete)

    def _update(self, done, total, label, complete):
        if label:
            self._current = label
        if self.cancel_token.is_set():
            self.task_text.SetLabel(f"Cancelling, waiting for {self._current} to finish...")
        elif label:
            self.task_text.SetLabel(f"Running: {label}")
        if complete:
            if self.timer.IsRunning():
                self.timer.Stop()
            self.gauge.SetRange(max(total, 1))
            self.gauge.SetValue(done)
            self.count_text.SetLabel(f"{done} of {total} tasks completed")
        else:
            self.count_text.SetLabel(f"{done} of {total} tasks completed so far")
        self.Layout()

    def OnCancel(self, event):
        if self.cancel_token.is_set():
            return
        self.cancel_token.set()
        self.cancel_button.Disable()
        task = self._current or "the running tasks"
        self.task_text.SetLabel(f"Cancelling, waiting for {task} to finish...")
        self.Layout()

    def _finished(self):
        self.timer.Stop()
        self.EndModal(wx.ID_CANCEL if self.cancel_token.is_set() else wx.ID_OK)


class RunCancelledDialog(wx.Dialog):
    """Tells the user that a run was cancelled and where its results are.

    Args:
        parent: parent window.
        title: name of the tool or workflow.
        run (flim.core.runner.FlowRun): the cancelled run.
    """

    def __init__(self, parent, title, run):
        super().__init__(parent, wx.ID_ANY, title=title)
        counts = run.task_counts()
        total = sum(counts.values())
        sizer = wx.BoxSizer(wx.VERTICAL)

        def text(label):
            sizer.Add(wx.StaticText(self, label=label), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        text(f"{title} was cancelled after {counts.get('completed', 0)} of {total} tasks.")
        self.results_dir = run.autosave_dir
        if self.results_dir:
            text("Results of the completed tasks are in:")
            path = wx.TextCtrl(self, value=self.results_dir, style=wx.TE_READONLY, size=(460, -1))
            sizer.Add(path, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        else:
            text("No results were saved because Autosave is off.")
        self.link = None
        if run.ui_url:
            text("Flow run on the Prefect server:")
            self.link = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, run.ui_url, run.ui_url)
            sizer.Add(self.link, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        sizer.Add(self.CreateButtonSizer(wx.OK), 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizerAndFit(sizer)
