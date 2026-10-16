import flim.core.configuration as cfg
from flim.core import parser


def test_fov_treatment_cell_parser():
    p = parser.fov_treatment_cell_parser()
    result = p.parsefilename("/data/run/Results_FOV1_WT_12.txt")
    assert result["Directory"] == "/data/run"
    assert result["File"] == "Results_FOV1_WT_12.txt"
    assert result["FOV"] == "FOV1"
    assert result["Treatment"] == "WT"
    assert result["Cell"] == "12"


def test_windows_paths_are_normalized():
    p = parser.fov_treatment_cell_parser()
    result = p.parsefilename("C:\\data\\Results_FOV1_WT_12.txt")
    assert result["Treatment"] == "WT"


def test_unused_patterns_are_skipped():
    p = parser.defaultparser()
    p.set_regexpatterns(
        [
            {cfg.CONFIG_PARSER_USE: True, cfg.CONFIG_PARSER_CATEGORY: "A", cfg.CONFIG_PARSER_REGEX: r"/(\w+)_"},
            {cfg.CONFIG_PARSER_USE: False, cfg.CONFIG_PARSER_CATEGORY: "B", cfg.CONFIG_PARSER_REGEX: r"_(\w+)\."},
        ]
    )
    result = p.parsefilename("/x/foo_bar.txt")
    assert result["A"] == "foo"
    assert "B" not in result
    assert list(p.compiledpatterns) == ["A"]


def test_no_parser():
    assert parser.no_parser().parsefilename("/x/foo_bar.txt") == {}
