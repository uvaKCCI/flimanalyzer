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
        assert "cannot be written to" in folder_problem(folder / "results")
    finally:
        folder.chmod(0o700)


def test_unreachable_drive(monkeypatch):
    # a drive the program does not see: neither the folder nor any parent exists
    monkeypatch.setattr(paths.os.path, "exists", lambda p: False)
    assert "cannot be reached" in folder_problem("/Volumes/share/results")


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


def test_tool_folders_are_stored_relative_to_the_default_folder(tmp_path):
    from pathlib import Path

    from flim.core.paths import resolved_folder, stored_folder

    default = tmp_path / "results"
    inside = default / "kmeans" / "run1"
    outside = tmp_path / "elsewhere"
    assert stored_folder(default, default) is None  # the default folder: none stored
    assert stored_folder(str(default) + os.sep, default) is None
    assert stored_folder(inside, default) == Path("kmeans", "run1")  # moves with it
    assert stored_folder(outside, default) == Path(canonical_folder(outside))
    assert stored_folder(tmp_path / "results2", default).is_absolute()  # not inside
    assert stored_folder("", default) is None
    # and back
    assert resolved_folder(None, default) == default
    assert resolved_folder(Path("kmeans", "run1"), tmp_path / "moved") == tmp_path / "moved" / "kmeans" / "run1"
    assert resolved_folder(outside, default) == outside


# --- file and folder names ---


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Summary: NAD(P)H a2[%]", "Summary_NAD_P_H_a2_pcent"),
        ("Autoencoder: Train", "Autoencoder_Train"),
        ("Order Category Values", "Order_Category_Values"),
        ("τm (ps)", "taum_ps"),
        ("µm", "um"),
        ("café", "cafe"),
        ("../etc/passwd", "etc_passwd"),  # no folders
        ("a\nb\r", "a_b"),
        ("Table_Concatenated", "Table_Concatenated"),
        ("...", "_"),
    ],
)
def test_path_name(name, expected):
    assert paths.path_name(name, paths.DEFAULT_CHAR_REPLACEMENTS) == expected


def test_path_name_uses_the_given_replacements_else_the_defaults():
    assert paths.path_name("a2[%]", {**paths.DEFAULT_CHAR_REPLACEMENTS, "%": "pct"}) == "a2_pct"
    assert paths.path_name("a2[%]") == "a2_pcent"  # the defaults


def test_same_names_ignore_case():
    names = ["a b.txt", "A_B.txt", "c.txt"]
    assert paths.same_names(names, paths.DEFAULT_CHAR_REPLACEMENTS) == [("a b.txt", "A_B.txt")]
