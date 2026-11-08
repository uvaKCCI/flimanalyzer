#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command-line entry point of flimanalyzer: parses the arguments and starts the GUI,
or batch mode with ``--batch``."""

import logging
import argparse
import sys
from flim._version import __version__
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
        help="data files to open in the GUI, each in its own window",
    )
    add_settings_options(parser)
    parser.add_argument(
        "-l",
        "--log",
        choices=LOG_LEVELS,
        default="info",
        help="logging level",
    )
    return parser


def parse_arguments(argv=None):
    """Parse the command line of flimanalyzer.

    Args:
        argv: The arguments; defaults to `sys.argv[1:]`.

    Returns:
        The parsed arguments.
    """
    return build_parser().parse_args(argv)


def interactive_run(fa, files=None, settings_manager=None):
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
        app.start(fa, settings_manager=settings_manager, files=files)
    else:
        app = FLIMAnalyzerApp(fa, settings_manager=settings_manager, files=files)
    app.MainLoop()


def choose_settings(check):
    """Ask the user how to use an app settings file some of whose settings cannot be
    used (flim.gui.settingscheck.choose_settings), before the main window opens.

    Args:
        check: The result of `check_settings_file`.

    Returns:
        The check whose sections to use, or None to use no file.

    Raises:
        ValueError: If wxPython is not installed (no dialog can be shown); the
            message lists the problems.
    """
    try:
        import wx
    except ImportError:
        raise ValueError(check.summary()) from None
    from flim.gui.app import FLIMAnalyzerApp
    from flim.gui.settingscheck import choose_settings as ask

    global _startup_app
    if not isinstance(wx.GetApp(), FLIMAnalyzerApp):
        # opens no window; interactive_run opens the main window. Kept referenced:
        # an app without a reference is destroyed at once.
        _startup_app = FLIMAnalyzerApp()
    return ask(check)


def init_logger(loglevel):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    numeric_level = getattr(logging, loglevel, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {loglevel}")
    logging.basicConfig(
        level=numeric_level,
        filename="flimanalyzer.log",
        filemode="w",
        format="%(levelname)s \t %(asctime)-15s - %(module)s.%(funcName)s: %(message)s",
    )
    logging.info(f"Log level: {numeric_level}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if "--batch" in argv:  # the other arguments are passed to flim.batch.main
        from flim import batch

        argv.remove("--batch")
        sys.exit(batch.main(argv))

    parser = build_parser()
    args = parser.parse_args(argv)
    init_logger(args.log.upper())
    logging.info(f"FLIMAnalyzer version {__version__}")
    logging.debug(args)
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
        )
        execution = ExecutionOptions(execution=manager.settings.execution)
        execution.check_available()
    except (FileNotFoundError, ValueError, RuntimeError) as err:
        parser.error(str(err))
    for note in notes + more:
        print(f"flimanalyzer: warning: {note}", file=sys.stderr)
        logging.warning(note)
    fa = FLIMAnalyzer(execution=execution)
    try:
        with use_prefect_server(start=manager.settings.prefect_server):
            interactive_run(fa, files=args.input, settings_manager=manager)
    except PrefectServerError as err:
        logging.error(err)
        show_startup_error(str(err))
        sys.exit(f"flimanalyzer: {err}")


def show_startup_error(message):
    """Shows a startup error in a message box, because the GUI may have been started
    without a console. Does nothing if wxPython is not installed."""
    try:
        import wx
    except ImportError:
        return
    app = wx.GetApp() or wx.App(False)  # noqa: F841  (needed for the message box)
    wx.MessageBox(message, "FLIMAnalyzer", wx.OK | wx.ICON_ERROR)


if __name__ == "__main__":  # python -m flim.analyzerapp; the command calls main()
    main()
