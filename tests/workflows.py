"""Workflow files for tests."""

import json


def import_with_preset(preset: str, name: str = None) -> dict:
    """Return the built-in Import workflow with a Separate Categories step of a
    built-in preset before Calculate, as a user would write it for a batch run.

    Args:
        preset: The preset's name, e.g. `FOV, Treatment, Cell`.
        name: The workflow's name; default: `Import: <preset>`.
    """
    from flim.core.categories import separate_presets
    from flim.core.workflowfile import BUILT_IN

    data = json.loads((BUILT_IN / "import.json").read_text())
    (settings,) = [p["settings"] for p in separate_presets() if p["name"] == preset]
    steps = data["steps"]
    calculate = next(i for i, s in enumerate(steps) if s["tool"] == "Calculate")
    steps.insert(calculate, {"tool": "Separate Categories", "config": dict(settings)})
    for number, step in enumerate(steps, 1):
        step["id"] = str(number)
    data["name"] = name or f"Import: {preset}"
    return data


def write_workflow(path, data: dict):
    """Write a workflow file; return its path."""
    path.write_text(json.dumps(data, indent=2))
    return path
