#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command-line entry point of flimanalyzer: starts the GUI or batch mode.

Parses the arguments and starts the GUI; with `--batch` or `--dry-run`, runs batch
mode (`flim.batch`) instead.
"""

import logging
import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from flim._version import __version__
from flim.core import logs
from flim.core.cli import add_settings_options, command_line_changes, settings_file
from flim.core.execution import ExecutionOptions
from flim.core.prefect_server import PrefectServerError, use_prefect_server
from flim.core.settingsmgr import (
    UserSettingsFile,
    session_settings,
    start_folder_settings,
    user_settings_path,
)
from flim.core.tools import FLIMAnalyzer

if TYPE_CHECKING:
    import logging.handlers

    from flim.core.settings import LogSettings, SettingsCheck
    from flim.core.settingsmgr import Pick, SettingsManager

logger = logging.getLogger(__name__)

LOG_LEVELS = ["debug", "info", "warning", "error", "critical"]
_startup_app = None  # the GUI app, if created for a dialog before the main window


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser of flimanalyzer.

    Returns:
        The parser, with the input files, the shared app settings options
        (`flim.core.cli`) and the log level.
    """
    parser = argparse.ArgumentParser(
        prog="flimanalyzer",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="flimanalyzer --batch ARGS runs flimbatch ARGS (batch mode, no GUI).",
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="+",
        help="data files or folders: opened, each in its own window, or read for\n"
        "--run and --workflow",
    )
    parser.add_argument(
        "-x", "--exclude", nargs="+", default=[], help="files not to read (names)"
    )
    parser.add_argument(
        "-r", "--run", action="append", default=[], metavar="NAME",
        help="tool or workflow to run on the files, also a workflow file by its name;\n"
        "its dialog (or, for a workflow file, its steps) is shown first",
    )  # fmt: skip
    parser.add_argument(
        "-w", "--workflow", action="append", default=[], metavar="FILE",
        help="workflow file to run on the files: a path, or a file name in the\n"
        "workflow search path",
    )  # fmt: skip
    parser.add_argument(
        "--dry-run", action="store_true",
        help="check the runs against the first rows of the files and exit (as flimbatch)",
    )  # fmt: skip
    add_settings_options(parser)
    parser.add_argument(
        "-l",
        "--log",
        choices=LOG_LEVELS,
        default="info",
        help="logging level",
    )
    return parser


def parse_arguments(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the command line of flimanalyzer.

    Args:
        argv: The arguments; defaults to `sys.argv[1:]`.

    Returns:
        The parsed arguments.
    """
    return build_parser().parse_args(argv)


def interactive_run(
    fa: FLIMAnalyzer,
    files: Optional[Sequence[str]] = None,
    settings_manager: Optional["SettingsManager"] = None,
    runs: Sequence[tuple[str, str]] = (),
    exclude: Sequence[str] = (),
) -> None:
    """Open the main window and run the GUI until it is closed.

    If the GUI app was already created for a dialog at startup, that app opens the
    main window; otherwise a new app is created.

    Args:
        fa: The FLIMAnalyzer object that provides the task runner and the execution
            settings.
        files: The data files or folders of `-i`, each opened in its own window, or
            read for the runs; None for none.
        settings_manager: The settings manager of the session; None for the GUI
            app's default.
        runs: The `--run` and `--workflow` arguments, as (`run` or `workflow`, name)
            pairs, run on the files at startup instead of opening them.
        exclude: The file names of `-x`, not read.

    Raises:
        SystemExit: If wxPython is not installed.
    """
    try:
        import wx  # noqa: F401
    except ImportError:
        sys.exit(
            "flimanalyzer: the GUI needs wxPython, which is not installed:"
            ' pip install "flimanalyzer[gui]". Without it, use flimbatch.'
        )
    import wx

    from flim.gui.app import FLIMAnalyzerApp  # here, so batch runs do not import wx

    app = wx.GetApp()
    if isinstance(app, FLIMAnalyzerApp):  # created for a dialog at startup
        app.runs, app.exclude = list(runs), list(exclude)
        app.start(fa, settings_manager=settings_manager, files=files)
    else:
        app = FLIMAnalyzerApp(
            fa, settings_manager=settings_manager, files=files, runs=runs, exclude=exclude
        )
    app.MainLoop()


def choose_settings(check: "SettingsCheck") -> Optional["SettingsCheck"]:
    """Ask how to use an app settings file some of whose settings cannot be used.

    The dialog (`flim.gui.settingscheck.choose_settings`) is shown before the main
    window opens.

    Args:
        check: The result of `check_settings_file`.

    Returns:
        The check whose sections to use, or None to use no file.

    Raises:
        ValueError: If wxPython is not installed (no dialog can be shown); the
            message lists the problems.
    """
    try:
        import wx  # noqa: F401
    except ImportError:
        raise ValueError(check.summary()) from None
    from flim.gui.settingscheck import choose_settings as ask

    _gui_app()
    return ask(check)


def _gui_app() -> None:
    """Create the GUI app for a dialog before the main window, if there is none."""
    import wx

    from flim.gui.app import FLIMAnalyzerApp

    global _startup_app
    if not isinstance(wx.GetApp(), FLIMAnalyzerApp):
        # opens no window; interactive_run opens the main window. Kept referenced:
        # an app without a reference is destroyed at once.
        _startup_app = FLIMAnalyzerApp()


def pick_app_settings(
    files: list[Path],
    default: Optional[Path] = None,
    warning: Optional[str] = None,
) -> "Pick":
    """Ask which app settings file to start with, before the main window opens.

    The dialog is `flim.gui.settingscheck.pick_app_settings`.

    Args:
        files: The files in the app settings search path.
        default: The default app settings file, preselected; None if none is set.
        warning: A message to show with the question; None for none.

    Returns:
        The file to start with and the default from now on; without wxPython, the
        default for both.
    """
    from flim.core.settingsmgr import Pick

    try:
        import wx  # noqa: F401
    except ImportError:
        return Pick(default, default)
    from flim.gui.settingscheck import pick_app_settings as ask

    _gui_app()
    return ask(files, default, warning)


def init_logger(loglevel: str) -> "logging.handlers.MemoryHandler":
    """Configure logging; records are kept in memory until `open_log`.

    Args:
        loglevel: The log level, e.g. `INFO`.

    Returns:
        The handler that keeps the records (see `flim.core.logs.begin`).

    Raises:
        ValueError: If the level is not a log level.
    """
    if not isinstance(getattr(logging, loglevel, None), int):
        raise ValueError(f"Invalid log level: {loglevel}")
    memory = logs.begin(loglevel)
    logger.info(f"Log level: {loglevel}")
    return memory


def open_log(
    memory: "logging.handlers.MemoryHandler", log: Optional["LogSettings"] = None
) -> tuple[Path, Optional[str]]:
    """Open the session's log file in the log folder, after removing old logs there.

    Args:
        memory: The handler returned by `init_logger`.
        log: The `log` settings; None for the defaults.

    Returns:
        The log file, and a message for the user if it is not in the log folder.
    """
    from flim.core.settings import LogSettings

    log = log or LogSettings()
    folder = log.dir.expanduser() if log.dir else logs.default_log_dir()
    logs.remove_old_logs(folder, log.max_age_days)
    return logs.open_log_file("flimanalyzer", folder, memory)


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Run flimanalyzer: start the GUI, or batch mode with `--batch` or `--dry-run`.

    In batch mode, the arguments without `--batch` go to `flim.batch.main`. For the
    GUI, the tools and workflows are registered, the settings of the session are
    read (with the dialogs of `choose_settings` and `pick_app_settings` where
    needed), the log file is opened, and the main window runs until it is closed.

    Args:
        argv: The arguments; defaults to `sys.argv[1:]`.

    Raises:
        SystemExit: In batch mode, with the exit code of `flim.batch.main`; with
            exit code 2 if the arguments or the settings are invalid; and with a
            message if the Prefect server cannot be used or wxPython is not
            installed.
    """
    argv = sys.argv[1:] if argv is None else list(argv)
    if "--batch" in argv or "--dry-run" in argv:  # flim.batch.main, without the GUI
        from flim import batch

        if "--batch" in argv:
            argv.remove("--batch")
        sys.exit(batch.main(argv))

    parser = build_parser()
    args = parser.parse_args(argv)
    memory = init_logger(args.log.upper())
    logger.info(f"FLIMAnalyzer version {__version__}")
    logger.debug(args)
    import flim.tools  # noqa: F401  (registers the tools: settings files are checked)
    import flim.workflow  # noqa: F401  (registers the workflows)
    from flim.core.registry import TOOLS_GROUP, discover

    discover(TOOLS_GROUP)  # the tools of other installed packages
    try:
        name, notes = settings_file(args)
        changes, more = command_line_changes(args)
        if name is None:
            path, note = start_folder_settings()
            if path is not None:
                name = str(path)
                more.append(note)
        manager = session_settings(
            name,
            changes,
            user_file=UserSettingsFile(user_settings_path()),
            choose=choose_settings,
            pick=pick_app_settings,
        )
        execution = ExecutionOptions(execution=manager.settings.execution)
        execution.check_available()
    except (FileNotFoundError, ValueError, RuntimeError) as err:
        logger.error(err)
        open_log(memory)  # the log folder setting may be what failed
        parser.error(str(err))
    _, notice = open_log(memory, manager.settings.log)
    if notice:
        manager.notices.append(notice)
    for note in notes + more + manager.notices:
        print(f"flimanalyzer: warning: {note}", file=sys.stderr)
        logger.warning(note)
    fa = FLIMAnalyzer(execution=execution)
    try:
        with use_prefect_server(start=manager.settings.prefect_server):
            runs = [("run", n) for n in args.run] + [("workflow", n) for n in args.workflow]
            interactive_run(
                fa, files=args.input, settings_manager=manager, runs=runs, exclude=args.exclude
            )
    except PrefectServerError as err:
        logger.error(err)
        show_startup_error(str(err))
        sys.exit(f"flimanalyzer: {err}")


def show_startup_error(message: str) -> None:
    """Show a startup error in a message box.

    The GUI may have been started without a console, where the message printed to
    standard error is not seen. Does nothing if wxPython is not installed.

    Args:
        message: The error message.
    """
    try:
        import wx
    except ImportError:
        return
    app = wx.GetApp() or wx.App(False)  # noqa: F841  (needed for the message box)
    wx.MessageBox(message, "FLIMAnalyzer", wx.OK | wx.ICON_ERROR)


if __name__ == "__main__":  # python -m flim.analyzerapp; the command calls main()
    main()
