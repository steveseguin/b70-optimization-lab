"""Host input roots for the relocatable diagnostic package.

Package members stay beside this file; repository inputs use SOURCE_REPO.
Absolute model/runtime/receipt paths retain their original identities.
"""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
configured = os.environ.get("SCREEN1B_SOURCE_REPO")
if (HERE / "diagnostic-stage.json").exists() and not configured:
    raise RuntimeError("staged package requires SCREEN1B_SOURCE_REPO")
REPO = (Path(configured) if configured else HERE.parents[2]).resolve()
LANE = REPO / "experiments/qwen38-flash-next-fp8-b70"


def repo_input(path):
    """Resolve repository-relative inputs independently of stage and cwd."""
    path = Path(path)
    return (path if path.is_absolute() else REPO / path).resolve()
