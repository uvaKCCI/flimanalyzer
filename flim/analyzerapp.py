#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  7 14:38:04 2018

@author: khs3z
"""

import os
import logging
import argparse
import sys
import flim
from flim._version import __version__
from flim.core.tools import FLIMAnalyzer, check_executor_available
from flim.core.prefect_server import use_prefect_server


def parse_arguments():
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        epilog="flimanalyzer --batch ARGS runs flimbatch ARGS (batch mode, no GUI)."
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="+",
        help="data files to open in the application, each in its own window",
    )
    parser.add_argument(
        "-e",
        "--executor",
        default="LocalExecutor",
        help=(
            "executor to run pipeline. Options: LocalExecutor, LocalDaskExecutor,"
            " DaskExecutor"
        ),
    )
    parser.add_argument(
        "-a",
        "--execargs",
        default="",
        help=(
            "comma separated list of arguments to pass to executor instance, e.g."
            " num_workers=4 (LocalExecutor: number of tasks run at the same time)"
        ),
    )
    parser.add_argument(
        "--no-prefect-server",
        action="store_true",
        help=(
            "don't start a local Prefect server if none is running; flows then use a"
            " temporary server"
        ),
    )
    parser.add_argument(
        "-c", "--config", default=None, help="settings file to start with (any version)"
    )
    parser.add_argument(
        "-l",
        "--log",
        choices=["info", "debug", "warning", "error", "critical"],
        default="info",
        help="logging level",
    )
    return parser.parse_args()


def interactive_run(fa, files=None, settings=None):
    try:
        import wx  # noqa: F401
    except ImportError:
        sys.exit(
            "flimanalyzer: the application needs wxPython, which is not installed:"
            ' pip install "flimanalyzer[gui]". Without it, use flimbatch.'
        )
    from flim.gui.app import FLIMAnalyzerApp  # here: batch runs never import wx

    app = FLIMAnalyzerApp(fa, config=settings, files=files)
    app.MainLoop()


def init_logger(loglevel):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    numeric_level = getattr(logging, loglevel, None)
    if not isinstance(numeric_level, int):
        raise ValueError("Invalid log level: %s" % args.log)
    logging.basicConfig(
        level=numeric_level,
        filename="flimanalyzer.log",
        filemode="w",
        format="%(levelname)s \t %(asctime)-15s - %(module)s.%(funcName)s: %(message)s",
    )
    logging.info(f"Log level: {numeric_level}")


def main():
    argv = sys.argv[1:]
    if "--batch" in argv:  # the rest is flimbatch's (flim/batch.py)
        from flim import batch

        argv.remove("--batch")
        sys.exit(batch.main(argv))
    # with open(os.path.join(os.path.dirname(__file__),"..","VERSION"), "r") as vf:
    #    __version__ = vf.read().strip()

    args = parse_arguments()
    try:
        check_executor_available(args.executor)
    except RuntimeError as e:
        sys.exit(f"flimanalyzer: {e}")
    init_logger(args.log.upper())
    version = __version__
    logging.info(f"FLIMAnalyzer version {version}")

    logging.debug(args)
    fa = FLIMAnalyzer(executor=args.executor, execargs=args.execargs)
    # analyzers = analysis.absanalyzer.init_analyzers()
    # aes = analysis.ml.autoencoder.init_autoencoders()
    # config = analysis.absanalyzer.init_default_config(analyzers)
    # print (config)
    settings = None
    if args.config:
        from flim.core.settings import load_settings

        settings = load_settings(args.config)
    with use_prefect_server(start=not args.no_prefect_server):
        interactive_run(fa, files=args.input, settings=settings)


if __name__ == "__main__":
    import platform, multiprocessing

    if platform.system() == "Darwin":
        multiprocessing.set_start_method("spawn")
    main()
