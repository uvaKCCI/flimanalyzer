"""The command-line options of the app settings (flim.core.cli)."""

import argparse
from pathlib import Path

import pytest

from flim.core.cli import (
    add_settings_options,
    command_line_changes,
    executor_settings,
    settings_file,
)


def parse(*argv, output_required=False):
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    add_settings_options(parser, output_required=output_required)
    return parser.parse_args(list(argv))


@pytest.mark.parametrize(
    "spec, expected",
    [
        (None, {"executor": "local", "workers": None}),
        ("local:workers=4", {"executor": "local", "workers": 4}),
        (
            "dask-local:workers=4,scheduler=processes",
            {"executor": "dask-local", "workers": 4, "scheduler": "processes", "kwargs": {}},
        ),
        # other keys of the Dask executors are further Dask arguments
        (
            "dask-local:threads_per_worker=2",
            {
                "executor": "dask-local",
                "workers": None,
                "scheduler": "threads",
                "kwargs": {"threads_per_worker": 2},
            },
        ),
        # the name ends at the first ":", so the address keeps its port
        (
            "dask:address=tcp://10.0.0.5:8786",
            {"executor": "dask", "address": "tcp://10.0.0.5:8786", "kwargs": {}},
        ),
    ],
)
def test_executor(spec, expected):
    assert executor_settings(spec) == (expected, [])


@pytest.mark.parametrize(
    "spec, message",
    [
        ("dask", "needs an address"),
        ("local:scheduler=processes", "local has no scheduler"),
        ("ray", "unknown executor 'ray'"),
        ("local:workers=0", "workers"),
        ("dask-local:scheduler=bogus", "scheduler"),
        ("local:workers", "is not KEY=VALUE"),
    ],
)
def test_invalid_executor(spec, message):
    with pytest.raises(ValueError, match=message):
        executor_settings(spec)


@pytest.mark.parametrize(
    "spec, execargs, expected, suggestion",
    [
        ("LocalExecutor", None, {"executor": "local", "workers": None}, "use -e local"),
        (
            "LocalExecutor",
            "num_workers=3",
            {"executor": "local", "workers": 3},
            "use -e local:workers=3",
        ),
        # without an address DaskExecutor started a local cluster, and still does
        (
            "DaskExecutor",
            None,
            {"executor": "dask-local", "workers": None, "scheduler": "threads", "kwargs": {}},
            "use -e dask-local",
        ),
        (
            "DaskExecutor",
            "address=tcp://h:8786",
            {"executor": "dask", "address": "tcp://h:8786", "kwargs": {}},
            "use -e dask:address=tcp://h:8786",
        ),
        (
            "LocalDaskExecutor",
            "num_workers=4,scheduler=processes",
            {"executor": "dask-local", "workers": 4, "scheduler": "processes", "kwargs": {}},
            "use -e dask-local:",
        ),
    ],
)
def test_deprecated_executor_forms(spec, execargs, expected, suggestion):
    settings, notes = executor_settings(spec, execargs)
    assert settings == expected
    assert "deprecated" in notes[0] and suggestion in notes[0]


def test_deprecated_forms_ignore_what_0_6_ignored():
    settings, notes = executor_settings("LocalExecutor", "num_workers=x,foo=1")
    assert settings == {"executor": "local", "workers": None}
    assert any("ignored workers=x" in n for n in notes)
    assert any("ignored foo" in n for n in notes)
    with pytest.raises(ValueError):  # the new syntax is strict
        executor_settings("local:foo=1")


def test_settings_file_from_s_or_deprecated_c():
    assert settings_file(parse("-s", "a.json")) == ("a.json", [])
    name, notes = settings_file(parse("-c", "a.json"))
    assert name == "a.json" and "deprecated" in notes[0]
    with pytest.raises(ValueError, match="give only -s"):
        settings_file(parse("-s", "a", "-c", "b"))


def test_only_given_options_become_changes():
    assert command_line_changes(parse()) == ({}, [])
    changes, notes = command_line_changes(
        parse("-o", "out", "--no-prefect-server", "--log-dir", "logs", "--cache-dir",
              "cache", "--no-strict", "-e", "local:workers=2")
    )
    assert notes == []
    assert changes == {
        "results_dir": "out",
        "prefect_server": False,
        "log": {"dir": "logs"},  # partial: the session settings complete it
        "cache": {"dir": "cache"},  # partial: the session settings complete it
        "strict": False,
        "execution": {"executor": "local", "workers": 2},
    }


def test_deprecated_allow_guesses_means_no_strict():
    args = parse()
    args.allow_guesses = True  # flimbatch's deprecated option
    changes, notes = command_line_changes(args)
    assert changes == {"strict": False} and "use --no-strict" in notes[0]


def test_output_can_be_required():
    with pytest.raises(SystemExit):
        parse(output_required=True)
    assert parse("-o", "out", output_required=True).output == "out"


def test_help_lists_the_executors(capsys):
    with pytest.raises(SystemExit):
        parse("--help")
    text = capsys.readouterr().out
    for line in ("local[:workers=N]", "dask-local[:workers=N,scheduler=threads|processes",
                 "dask:address=URL", "--strict, --no-strict", "--cache-dir DIR"):
        assert line in text
    assert "--config" not in text and "--execargs" not in text  # deprecated: hidden


def test_paths_stay_text_until_validated():
    # the settings models turn them into Path objects
    from flim.core.settingsmgr import session_settings

    changes, _ = command_line_changes(parse("-o", "out"))
    assert session_settings(None, changes).settings.results_dir == Path("out")
