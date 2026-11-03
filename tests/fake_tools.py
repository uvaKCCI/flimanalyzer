"""Fake tools for runner and progress tests: instead of sleeping fixed times, they run
until the test has seen what it needs (an event) or cancels the run."""

import threading
import time
from typing import Optional

from flim.core.config import TaskConfig
from flim.core.tool import Tool

WAIT = 10  # seconds: the longest any fake tool or test waits for an event


class FakeConfig(TaskConfig):
    marker: Optional[str] = None  # file created when the task starts


class Counter(Tool[FakeConfig]):
    """Counts its runs in a list shared by all copies."""

    name = "Counter"
    category = "Data"

    def __init__(self, name=None, calls=None):
        super().__init__()
        if name:
            self.name = name
        self.calls = calls if calls is not None else []

    def run(self, *inputs, config):
        self.calls.append(self.name)
        return {f"{self.name} done": True}


class Waiter(Counter):
    """Sets ``started`` when it runs, then runs until ``release`` is set or (if
    ``cancellable``) the run is cancelled; fails after WAIT seconds.

    Events cannot be passed to other processes: there, without events, it waits to be
    cancelled (``config.marker`` tells the test it started).
    """

    def __init__(
        self, name=None, calls=None, started=None, release=None, cancellable=True
    ):
        super().__init__(name, calls)
        self.started = started
        self.release = release
        self.cancellable = cancellable

    def run(self, *inputs, config):
        self.calls.append(self.name)
        if config.marker:
            open(config.marker, "w").close()  # also in other processes
        if self.started is not None:
            self.started.set()
        release = self.release or threading.Event()
        end = time.monotonic() + WAIT
        while not release.wait(0.01):
            if self.cancellable:
                self.check_cancelled()
            if time.monotonic() > end:
                raise TimeoutError(f"{self.name}: not released or cancelled in {WAIT} s")
        return {f"{self.name} done": True}


def wait_for(event, what="the event"):
    """Waits for ``event`` (at most WAIT seconds); fails clearly if it is not set."""
    assert event.wait(WAIT), f"{what} did not happen within {WAIT} s"
