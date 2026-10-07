#!/usr/bin/env python3
"""Replay frozen prefill evidence after proving declared current-source drift.

The original verifier and its manifest remain untouched. A temporary source
view supplies exact historical bytes, never rewritten hashes, to that verifier.
Current serving acceptance remains pending for every drifted input.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

from source_drift_proofs import PROOFS

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "experiments/qwen38-27b-b70/data/2026-09-14-fp8-prefill-focus"
VERIFIER = "experiments/qwen38-27b-b70/scripts/verify-fp8-prefill-evidence.py"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_source(root, row, declarations):
    relative = row["repository_path"]
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("source must be a safe repository-relative path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("source outside repository")
    current = path.read_bytes()
    if digest(current) == row["sha256"] and len(current) == row["bytes"]:
        return current, None
    entry = declarations.get(relative)
    if not entry:
        raise ValueError("undeclared source drift: " + relative)
    if (entry.get("frozen_sha256") != row["sha256"] or
            entry.get("current_sha256") != digest(current) or
            entry.get("acceptance") != "pending" or not entry.get("reason") or not entry.get("retire_by")):
        raise ValueError("invalid source-drift binding: " + relative)
    frozen_path = (root / entry["frozen_source"]).resolve()
    if not frozen_path.is_relative_to(root.resolve()):
        raise ValueError("historical source outside repository")
    frozen = frozen_path.read_bytes()
    if digest(frozen) != row["sha256"] or len(frozen) != row["bytes"]:
        raise ValueError("historical source does not match frozen manifest")
    # This replay only admits the reviewed metadata addition, never verifier
    # changes or an unrelated source change under a broad allow-list.
    if entry["proof"]["kind"] != "model_metadata_addition" or not relative.endswith("/model-direct.json"):
        raise ValueError("unsupported prefill source drift")
    PROOFS["model_metadata_addition"](entry, frozen, current)
    return frozen, entry


def main():
    manifest = json.loads((PACKET / "evidence/manifest.json").read_text())
    declaration = json.loads((PACKET / "source-drift.json").read_text())
    entries = {e["path"]: e for e in declaration["entries"]}
    if len(entries) != len(declaration["entries"]):
        raise ValueError("duplicate drift declaration")
    pending = []
    with tempfile.TemporaryDirectory(prefix="fp8-prefill-historical-source-") as temporary:
        source_root = Path(temporary)
        for row in manifest["source_files"]:
            content, drift = checked_source(ROOT, row, entries)
            destination = source_root / row["repository_path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            if drift:
                pending.append(drift)
        if VERIFIER not in {r["repository_path"] for r in manifest["source_files"]}:
            raise ValueError("verifier not pinned by source manifest")
        spec = importlib.util.spec_from_file_location("frozen_prefill_verifier", source_root / VERIFIER)
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        result = verifier.verify(PACKET)
    print(json.dumps({"frozen_evidence": result, "current_source_acceptance": "pending" if pending else "unchanged",
                      "declared_drift": pending, "new_model_execution": False}, indent=2))


if __name__ == "__main__":
    main()
