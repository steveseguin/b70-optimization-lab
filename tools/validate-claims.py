#!/usr/bin/env python3
"""Validate claims/*.json against the registry schema (claims/README.md).

Runs in CI on every PR and locally:  python3 tools/validate-claims.py
Stdlib only; exits non-zero and prints one line per problem.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAIMS = ROOT / "claims"

STATUSES = {
    "submitted", "queued", "reproducing",
    "confirmed", "confirmed-adjusted", "refuted", "stale",
    "lab-verified",
}
NEEDS_VERIFICATION = {"confirmed", "confirmed-adjusted", "refuted", "stale", "lab-verified"}
DATE_RE = re.compile(r"^\d{4}(-\d{2}){0,2}$")
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def err(path, problems, msg):
    problems.append(f"{path.name}: {msg}")


def check(path, problems):
    try:
        c = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        err(path, problems, f"invalid JSON: {e}")
        return

    cid = c.get("id")
    if not cid or not isinstance(cid, str) or not ID_RE.match(cid):
        err(path, problems, "id missing or not lowercase-hyphenated")
    elif path.name != f"{cid}.json":
        err(path, problems, f"id {cid!r} does not match filename")

    if not c.get("model"):
        err(path, problems, "model missing")

    recipe = c.get("recipe")
    if not isinstance(recipe, dict):
        err(path, problems, "recipe missing")
    else:
        for k in ("engine", "quant"):
            if not recipe.get(k):
                err(path, problems, f"recipe.{k} missing")
        if "speedup" not in recipe:
            err(path, problems, "recipe.speedup key missing (use null when none)")
        for k in ("cards", "tp"):
            v = recipe.get(k)
            if not isinstance(v, int) or v < 1:
                err(path, problems, f"recipe.{k} must be a positive integer")

    claimed = c.get("claimed")
    if not isinstance(claimed, dict):
        err(path, problems, "claimed missing")
    else:
        if not isinstance(claimed.get("tok_s"), (int, float)) or claimed["tok_s"] <= 0:
            err(path, problems, "claimed.tok_s must be a positive number")
        for k in ("metric", "date", "by"):
            if not claimed.get(k):
                err(path, problems, f"claimed.{k} missing")
        if claimed.get("date") and not DATE_RE.match(str(claimed["date"])):
            err(path, problems, "claimed.date must be YYYY, YYYY-MM, or YYYY-MM-DD")
        ev = claimed.get("evidence")
        if ev and not (ROOT / ev).exists():
            err(path, problems, f"claimed.evidence path does not exist: {ev}")
        if claimed.get("by") != "lab" and not (c.get("submitter") or c.get("upstream")):
            err(path, problems, "outside claim needs submitter.url and/or upstream.repo")

    status = c.get("status")
    if status not in STATUSES:
        err(path, problems, f"status must be one of {sorted(STATUSES)}")

    ver = c.get("verification")
    if status in NEEDS_VERIFICATION:
        if not isinstance(ver, dict):
            err(path, problems, f"status {status!r} requires a verification block")
        else:
            if not isinstance(ver.get("tok_s"), (int, float)) or ver["tok_s"] <= 0:
                err(path, problems, "verification.tok_s must be a positive number")
            for k in ("metric", "date", "evidence"):
                if not ver.get(k):
                    err(path, problems, f"verification.{k} missing")
            ev = ver.get("evidence")
            if ev and not (ROOT / ev).exists():
                err(path, problems, f"verification.evidence path does not exist: {ev}")
    elif ver is not None and status in {"submitted", "queued"}:
        err(path, problems, f"status {status!r} must not have a verification block yet")

    hist = c.get("history")
    if not isinstance(hist, list) or not hist:
        err(path, problems, "history must be a non-empty list")
    else:
        for i, h in enumerate(hist):
            if not isinstance(h, dict) or not h.get("date") or not h.get("event"):
                err(path, problems, f"history[{i}] needs date and event")
            elif not DATE_RE.match(str(h["date"])):
                err(path, problems, f"history[{i}].date must be YYYY, YYYY-MM, or YYYY-MM-DD")


def main():
    paths = sorted(CLAIMS.glob("*.json"))
    if not paths:
        print("no claim files found")
        return 1
    problems = []
    for p in paths:
        check(p, problems)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {len(paths)} claims valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
