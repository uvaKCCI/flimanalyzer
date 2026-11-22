"""Scripts used by the CI workflows (.github/scripts)."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "image-version.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


@pytest.mark.parametrize(
    "version, suffix, expected",
    [
        ("0.6.2-cpu", "-cpu", "0.6.2"),  # CPU variant of a release
        ("0.6.2", "", "0.6.2"),  # CUDA variant (no suffix)
        ("0.6.2", "-cpu", "0.6.2"),  # suffix not present: unchanged
        ("dev-cpu", "-cpu", "dev"),  # branch build
    ],
)
def test_image_version_drops_the_variant_suffix(version, suffix, expected):
    out = subprocess.run(
        ["bash", str(SCRIPT), version, suffix], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == expected


def test_docker_workflow_takes_the_version_from_the_script():
    # regression: the version label kept the variant suffix, and the CPU image was
    # not published
    workflow = (ROOT / ".github" / "workflows" / "docker.yml").read_text()
    assert ".github/scripts/image-version.sh" in workflow
    assert 'echo "VERSION=${{ steps.meta.outputs.version }}"' not in workflow


NEWEST = ROOT / ".github" / "scripts" / "is-newest-release.sh"


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
@pytest.mark.parametrize(
    "tag, expected",
    [
        ("v0.7.0", "true"),  # the highest release
        ("v0.6.3", "false"),  # a release of an older series, after 0.7.0
        ("v0.10.0", "false"),  # not a tag of the repository
        ("v0.7.0rc1", "false"),  # not a release version
        ("dev", "false"),  # a branch
    ],
)
def test_only_the_highest_release_moves_latest(tmp_path, tag, expected):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q")
    git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "--allow-empty", "-m", "x")
    for t in ("v0.6.2", "v0.7.0", "v0.6.3", "v0.7.0rc1", "v0.9"):  # 0.6.3 tagged last
        git("tag", t)
    out = subprocess.run(
        ["bash", str(NEWEST), tag], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == expected


def test_docker_workflow_moves_latest_only_for_the_highest_release():
    workflow = (ROOT / ".github" / "workflows" / "docker.yml").read_text()
    assert ".github/scripts/is-newest-release.sh" in workflow
    assert "steps.newest.outputs.latest == 'true'" in workflow
