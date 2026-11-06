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
    # the 0.6.1 CPU image wasn't published: its version label kept the suffix
    workflow = (ROOT / ".github" / "workflows" / "docker.yml").read_text()
    assert ".github/scripts/image-version.sh" in workflow
    assert 'echo "VERSION=${{ steps.meta.outputs.version }}"' not in workflow
