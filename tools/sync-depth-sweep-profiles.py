#!/usr/bin/env python3
"""Promote measured llama-bench depth sweeps into package profiles.

This tool never interpolates. Every emitted marker comes from one exact row in
the package's cited sweep JSON. Depth zero remains in the raw evidence because
the public performance-profile schema currently requires positive context.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def measured_profiles(repo: Path, package: dict[str, Any]) -> list[dict[str, Any]]:
    curve = package.get("library", {}).get("context_curve")
    if not isinstance(curve, dict):
        raise ValueError("package has no library.context_curve to migrate")

    evidence = curve.get("evidence")
    scope = curve.get("scope")
    if not isinstance(evidence, str) or not evidence.startswith("repro/"):
        raise ValueError("context_curve.evidence must be an in-repo repro path")
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("context_curve.scope must be non-empty")

    rows = load_json(repo / evidence)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{evidence}: expected a non-empty JSON row list")

    by_metric: dict[str, dict[int, dict[str, Any]]] = {
        "decode": {},
        "prefill": {},
    }
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{evidence}: every row must be an object")
        depth = row.get("n_depth")
        prompt = row.get("n_prompt")
        generated = row.get("n_gen")
        value = row.get("avg_ts")
        samples = row.get("samples_ts")
        if not isinstance(depth, int) or depth < 0:
            raise ValueError(f"{evidence}: invalid n_depth {depth!r}")
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"{evidence}: invalid avg_ts at depth {depth}")
        if not isinstance(samples, list) or len(samples) < 2:
            raise ValueError(f"{evidence}: need at least two samples at depth {depth}")
        if prompt == 2048 and generated == 0:
            metric = "prefill"
        elif prompt == 0 and generated == 128:
            metric = "decode"
        else:
            raise ValueError(
                f"{evidence}: unexpected benchmark shape at depth {depth}: "
                f"n_prompt={prompt!r}, n_gen={generated!r}"
            )
        if depth in by_metric[metric]:
            raise ValueError(f"{evidence}: duplicate {metric} depth {depth}")
        by_metric[metric][depth] = row

    decode_depths = sorted(by_metric["decode"])
    prefill_depths = sorted(by_metric["prefill"])
    if decode_depths != prefill_depths:
        raise ValueError(f"{evidence}: decode and prefill depths differ")
    positive_depths = [depth for depth in decode_depths if depth > 0]
    if len(positive_depths) < 2:
        raise ValueError(f"{evidence}: fewer than two positive measured depths")

    def points(metric: str) -> list[dict[str, Any]]:
        return [
            {
                "context_tokens": depth,
                "value": by_metric[metric][depth]["avg_ts"],
                "samples": len(by_metric[metric][depth]["samples_ts"]),
            }
            for depth in positive_depths
        ]

    zero_note = (
        " The directly measured zero-depth point remains in the linked raw "
        "evidence; no missing depth is interpolated."
    )
    return [
        {
            "id": "decode-vs-context-depth",
            "label": "Raw decode over existing context depth",
            "metric": "decode",
            "unit": "tok/s",
            "x_label": "Existing context depth before tg128",
            "scope": scope.rstrip(".") + "." + zero_note,
            "evidence": evidence,
            "points": points("decode"),
        },
        {
            "id": "prefill-vs-context-depth",
            "label": "Raw pp2048 over existing context depth",
            "metric": "prefill",
            "unit": "tok/s",
            "x_label": "Existing context depth before pp2048",
            "scope": scope.rstrip(".") + "." + zero_note,
            "evidence": evidence,
            "points": points("prefill"),
        },
    ]


def migrate(repo: Path, path: Path, write: bool) -> bool:
    package = load_json(path)
    profiles = measured_profiles(repo, package)

    library = dict(package["library"])
    library.pop("context_curve")
    migrated: dict[str, Any] = {}
    inserted = False
    for key, value in package.items():
        migrated[key] = library if key == "library" else value
        if key == "contributors":
            migrated["performance_profiles"] = profiles
            inserted = True
    if not inserted:
        migrated["performance_profiles"] = profiles

    rendered = json.dumps(migrated, indent=1, ensure_ascii=False) + "\n"
    changed = rendered != path.read_text(encoding="utf-8")
    if write and changed:
        path.write_text(rendered, encoding="utf-8")
    print(f"{'updated' if write and changed else 'checked'} {path.relative_to(repo)}")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packages", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    changed = False
    for path in args.packages:
        absolute = path if path.is_absolute() else repo / path
        changed |= migrate(repo, absolute, args.write)
    return 0 if args.write or not changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
