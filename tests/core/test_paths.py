import os

import pytest

from flim.core import paths
from flim.core.paths import canonical_folder, folder_problem, shorten_path


@pytest.mark.skipif(os.name == "nt", reason="symbolic links need extra rights")
def test_canonical_folder_is_absolute_with_links_resolved(tmp_path, monkeypatch):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real)
    monkeypatch.chdir(tmp_path)
    assert canonical_folder("link") == str(real)
    assert canonical_folder("link/new") == str(real / "new")  # need not exist yet
    monkeypatch.setenv("HOME", str(tmp_path))
    assert canonical_folder("~/real") == str(real)
    assert canonical_folder("") == "" and canonical_folder(None) is None


def test_mapped_drive_becomes_its_unc_path(monkeypatch):
    # what os.path.realpath returns on Windows for a mapped network drive
    unc = {r"Z:\results": r"\\server\share\results"}
    monkeypatch.setattr(paths.os.path, "abspath", lambda p: p)
    monkeypatch.setattr(paths.os.path, "realpath", lambda p: unc.get(p, p))
    assert canonical_folder(r"Z:\results") == r"\\server\share\results"


def test_unresolvable_folder_stays_absolute(monkeypatch):
    def realpath(p):
        raise OSError("drive not available")

    monkeypatch.setattr(paths.os.path, "realpath", realpath)
    assert canonical_folder("results") == os.path.abspath("results")


def test_usable_folders(tmp_path):
    assert folder_problem(tmp_path) is None
    assert folder_problem(tmp_path / "new" / "sub") is None  # created when saving


def test_a_file_is_no_folder(tmp_path):
    (tmp_path / "file").write_text("x")
    assert "is not a folder" in folder_problem(tmp_path / "file" / "sub")


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="permissions")
def test_read_only_folder(tmp_path):
    folder = tmp_path / "ro"
    folder.mkdir()
    folder.chmod(0o500)
    try:
        assert "can't be written to" in folder_problem(folder / "results")
    finally:
        folder.chmod(0o700)


def test_unreachable_drive(monkeypatch):
    # a drive the program doesn't see: neither the folder nor any parent exists
    monkeypatch.setattr(paths.os.path, "exists", lambda p: False)
    assert "can't be reached" in folder_problem("/Volumes/share/results")


@pytest.mark.parametrize(
    "path, short",
    [
        ("/short/path", "/short/path"),
        (
            "/Users/mst3k/Documents/projects/flim/results/2026-11-02_17-03-41/Summarize/",
            "/Users/mst3k/.../2026-11-02_17-03-41/Summarize/",
        ),
        (
            r"C:\Users\mst3k\Documents\projects\flim\results\2026-11-02_17-03-41\Summarize",
            r"C:\Users\mst3k\...\2026-11-02_17-03-41\Summarize",
        ),
        (
            r"\\server\share\lab\projects\flim\results\2026-11-02_17-03-41\Summarize",
            r"\\server\share\...\2026-11-02_17-03-41\Summarize",
        ),
    ],
)
def test_shorten_path(path, short):
    assert shorten_path(path) == short
    assert len(shorten_path(path)) <= 50


def test_shorten_path_keeps_the_last_folder():
    path = "/Users/mst3k/" + "a" * 60
    assert shorten_path(path) == path  # nothing to leave out
