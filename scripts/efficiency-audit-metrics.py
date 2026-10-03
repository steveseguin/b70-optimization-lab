#!/usr/bin/env python3
"""Objective lane-efficiency metrics from git history and committed campaign files.

Read-only. Works from any clone; needs no bench-results mount. Produces JSON
plus a markdown summary that the scheduled efficiency auditor (and humans)
reason from, so every audit measures the same things.

Metrics per window (default: last 7 days):
- commits by Git author name and per day, with separate co-author counts
- campaigns: prereg-to-result latency, outcome class from the result's
  ``status``/``decision`` text, arms per lane per day
- infrastructure events mentioned in results/notes (fault, reset, lockup,
  freeze, coredump, reboot)
- process-rule signals: speed verdicts from a single server, oracle-gated
  kernel changes, layer-local bisection runs (heuristic keyword scans)
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

OUTCOME_RULES = [
    ("accepted", r"promot|accept|qualified|passes|pass-|passed"),
    ("aborted-infra", r"abort|lockup|freeze|device lost|fault|reset|coredump"),
    ("rejected", r"reject|negative|closed|fail|miss|invalid"),
]
INFRA_RE = re.compile(r"fault response|CAT error|engine reset|soft lockup|host froze|coredump|reboot", re.I)
SINGLE_SERVER_SPEED_RE = re.compile(r"(one|single)[- ]server.*(tok/s|throughput|floor)|throughput floor failed", re.I)
FROZEN_ORACLE_RE = re.compile(r"frozen (natural |explicit deterministic )?(mtp0 )?oracle", re.I)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def author_class(name: str, email: str) -> str:
    s = f"{name} {email}".lower()
    if "claude" in s:
        return "claude"
    if "codex" in s or "openai" in s:
        return "codex"
    return "other"


_ADDED: dict[str, dt.datetime] = {}


def index_added_files(repo: Path, since: dt.datetime) -> None:
    """One history pass: path -> commit time at which it was first added in the window."""
    _ADDED.clear()
    out = git(repo, "log", f"--since={since.isoformat()}", "--diff-filter=A", "--name-only", "--format=%x00%cI")
    current = None
    for line in out.splitlines():
        if line.startswith("\x00"):
            current = dt.datetime.fromisoformat(line[1:])
        elif line.strip() and current is not None:
            _ADDED[line.strip()] = min(_ADDED.get(line.strip(), current), current)


def first_commit_time(repo: Path, path: str) -> dt.datetime | None:
    return _ADDED.get(path)


def outcome(text: str) -> str:
    t = text.lower()
    for label, pat in OUTCOME_RULES:
        if re.search(pat, t):
            return label
    return "unclassified"


def result_outcome(data: dict) -> tuple[str, str]:
    """Use campaign-level decisions, never successful subtests inside a failure."""
    closure = data.get("closure")
    status = " ".join(str(d.get(k, "")) for d in
                      ([closure, data] if isinstance(closure, dict) else [data])
                      for k in ("status", "decision", "classification", "outcome"))
    if re.search(OUTCOME_RULES[1][1], status, re.I):
        return "aborted-infra", status
    if re.search(r"not (?:passed|promoted|qualified)|do not promote|unqualified|reject|negative|closed|fail|miss|invalid", status, re.I):
        return "rejected", status
    if data.get("passed") is False:
        return "rejected", status
    if data.get("passed") is True or data.get("promoted") is True:
        return "accepted", status
    return outcome(status), status


def campaign_slug(path: Path) -> str:
    stem = re.sub(r"(?:[-_](?:prereg(?:istration)?|results?|summary))(?:[-_].*)?$", "", path.stem)
    return path.parent.name if stem in ("prereg", "preregistration", "result", "results", "summary") else stem


def discover_campaigns(repo: Path, since: dt.datetime, tracked: list[str]) -> list[dict]:
    """Join recursive, tracked records by lane + explicit ID or directory/slug.

    An exact slug also joins notes to data directories. Arbitrary prose is not
    interpreted as a result unless it has that identity; ambiguous notes stay
    unclassified. Only newly committed campaigns belong to the window.
    """
    records = []
    for rel in tracked:
        p = Path(rel)
        if len(p.parts) < 4 or p.parts[0] != "experiments" or p.parts[2] not in ("data", "notes"):
            continue
        prereg = bool(re.search(r"(?:^|[-_])prereg(?:istration)?(?:[-_.]|$)", p.name))
        result = p.suffix == ".json" and (p.name == "summary.json" or bool(re.search(r"(?:^|[-_])results?(?:[-_.]|$)", p.name)))
        if p.suffix not in (".json", ".md") or not (prereg or result or p.parts[2] == "notes"):
            continue
        records.append({"path": rel, "lane": p.parts[1], "slug": campaign_slug(p),
                        "prereg": prereg, "result": result})

    # Read only lanes active in this window, avoiding unrelated historical data.
    active_lanes = {r["lane"] for r in records if r["path"] in _ADDED}
    groups: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    aliases: dict[tuple[str, str], str] = {}
    for r in records:
        if r["lane"] not in active_lanes:
            continue
        p = repo / r["path"]
        r["data"] = {}
        r["text"] = ""
        try:
            if p.suffix == ".json":
                data = json.loads(p.read_text())
                r["data"] = data if isinstance(data, dict) else {}
            else:
                r["text"] = p.read_text(errors="replace")
        except (OSError, ValueError):
            r["text"] = "unreadable"
        identity = next((r["data"][k] for k in ("campaign_id", "campaign")
                         if isinstance(r["data"].get(k), str) and r["data"][k]), None)
        if identity:
            aliases[(r["lane"], r["slug"])] = identity
        r["identity"] = identity
    for r in records:
        if r["lane"] in active_lanes:
            identity = r["identity"] or aliases.get((r["lane"], r["slug"]), r["slug"])
            # Some cross-day result notes name their preregistration explicitly
            # but use an entirely different title. Join only an unambiguous link.
            if not r["prereg"] and r["text"]:
                refs = re.findall(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?Preregistration(?:\*\*)?:\s*(.+)$", r["text"])
                matches = [p for p in records if p["lane"] == r["lane"] and p["prereg"]
                           and any(Path(p["path"]).name in ref for ref in refs)]
                if len(matches) == 1:
                    p = matches[0]
                    identity = p["identity"] or aliases.get((p["lane"], p["slug"]), p["slug"])
            groups[(r["lane"], identity)].append(r)

    campaigns = []
    for (lane, identity), rows in sorted(groups.items()):
        preregs = [r for r in rows if r["prereg"]]
        results = [r for r in rows if not r["prereg"] and (r["result"] or preregs)]
        if not preregs and not any(Path(r["path"]).name == "summary.json" for r in results):
            continue
        starts = [_ADDED[r["path"]] for r in preregs if r["path"] in _ADDED]
        ends = [_ADDED[r["path"]] for r in results if r["path"] in _ADDED]
        # An older prereg must not become a newly started campaign on result day.
        if preregs and (not starts or any(r["path"] not in _ADDED for r in preregs)):
            continue
        t0 = min(starts) if starts else None
        t1 = min(ends) if ends else None
        if not (t0 or t1) or (t0 or t1) < since:
            continue
        # Prefer an aggregate JSON over a same-identity narrative note.
        results.sort(key=lambda r: (Path(r["path"]).suffix != ".json", r["path"]))
        oc, status = "no-result-yet", ""
        if results:
            r = results[0]
            oc, status = result_outcome(r["data"]) if r["data"] else (outcome(r["text"]), r["text"])
        campaigns.append({
            "lane": lane, "campaign": identity,
            "prereg_committed": t0.isoformat() if t0 else None,
            "result_committed": t1.isoformat() if t1 else None,
            "latency_hours": round((t1 - t0).total_seconds() / 3600, 2) if t0 and t1 and t1 >= t0 else None,
            "outcome": oc,
            "single_server_speed_verdict": bool(SINGLE_SERVER_SPEED_RE.search(status)),
            "frozen_oracle_gate": bool(FROZEN_ORACLE_RE.search(status)),
            "prereg_files": sorted(r["path"] for r in preregs),
            "result_files": sorted(r["path"] for r in results),
        })
    return campaigns


def commit_age(repo: Path, now: dt.datetime, path: str | None = None) -> float | None:
    timestamp = git(repo, "log", "-1", "--format=%cI", *(["--", path] if path else [])).strip()
    return round((now - dt.datetime.fromisoformat(timestamp)).total_seconds() / 86400, 3) if timestamp else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", type=Path, help="also write the JSON report to this file")
    ap.add_argument("--markdown", type=Path)
    ap.add_argument("--unshallow", action="store_true", help="allow git fetch --unshallow when history is shallow")
    ap.add_argument("--allow-shallow", action="store_true", help="allow incomplete history, with a JSON warning")
    a = ap.parse_args()
    repo = a.repo
    shallow = git(repo, "rev-parse", "--is-shallow-repository").strip() == "true"
    if shallow and a.unshallow:
        try:
            git(repo, "fetch", "--unshallow")
        except subprocess.CalledProcessError:
            ap.error("git fetch --unshallow failed; cannot trust incomplete history")
        shallow = git(repo, "rev-parse", "--is-shallow-repository").strip() == "true"
    warnings = []
    if shallow:
        if not a.allow_shallow:
            ap.error("shallow repository: use --unshallow to fetch history, or --allow-shallow for incomplete metrics")
        warnings.append("Shallow history: commit counts, campaign dates, and commit ages may be incomplete or misleading.")
        print(f"warning: {warnings[0]}", file=sys.stderr)
    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=a.days)
    index_added_files(repo, since)

    # commits
    log = git(repo, "log", f"--since={since.isoformat()}", "--format=%H%x1f%cI%x1f%an%x1f%ae%x1f%s%x1f%b%x1e")
    commits = []
    for rec in log.split("\x1e"):
        if not rec.strip():
            continue
        h, ci, an, ae, subj, body = (rec.strip("\n").split("\x1f") + [""] * 6)[:6]
        co_authors = set(re.findall(r"^Co-Authored-By:\s*(.*?)\s*<[^>]+>\s*$", body, re.I | re.M))
        commits.append({"hash": h[:9], "time": ci, "author": an, "subject": subj,
                        "author_class": author_class(an, ae), "co_authors": co_authors})
    commits.sort(key=lambda c: c["time"])
    by_author = collections.Counter(c["author"] for c in commits)
    co_authors = collections.Counter(name for c in commits for name in c["co_authors"])
    per_day = collections.Counter(c["time"][:10] for c in commits)
    gaps = []
    for x, y in zip(commits, commits[1:]):
        gaps.append((dt.datetime.fromisoformat(y["time"]) - dt.datetime.fromisoformat(x["time"])).total_seconds() / 3600)
    long_gaps = sorted(gaps, reverse=True)[:5]

    # campaigns
    tracked = git(repo, "ls-files", "-z", "--", "experiments").strip("\0").split("\0")
    campaigns = discover_campaigns(repo, since, tracked)
    lanes = collections.defaultdict(lambda: collections.Counter())
    for campaign in campaigns:
        lanes[campaign["lane"]][campaign["outcome"]] += 1
    lat = [c["latency_hours"] for c in campaigns if c["latency_hours"] is not None]

    # infra events in notes/results within window
    infra = []
    for p in list(repo.glob("experiments/*/notes/*.md")) + list(repo.glob("experiments/*/data/*result*.json")):
        t = first_commit_time(repo, str(p.relative_to(repo)))
        if not t or t < since:
            continue
        try:
            txt = p.read_text(errors="replace")
        except Exception:
            continue
        n = len(INFRA_RE.findall(txt))
        if n:
            infra.append({"file": str(p.relative_to(repo)), "mentions": n, "committed": t.isoformat()})

    summary = {
        "window_days": a.days, "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "commits_total": len(commits), "commits_by_author": dict(by_author), "commits_per_day": dict(sorted(per_day.items())),
        "co_authors": dict(co_authors),
        "commits_by_author_class": dict(collections.Counter(c["author_class"] for c in commits)),
        "shallow": shallow, "warnings": warnings,
        "days_since_last_commit": commit_age(repo, now),
        "days_since_last_commit_by_lane": {lane: commit_age(repo, now, f"experiments/{lane}")
                                           for lane in sorted({Path(p).parts[1] for p in tracked if len(Path(p).parts) >= 3})},
        "longest_commit_gaps_hours": [round(g, 1) for g in long_gaps],
        "campaigns_total": len(campaigns), "campaigns_by_lane_outcome": {k: dict(v) for k, v in lanes.items()},
        "prereg_to_result_latency_hours": {"median": round(sorted(lat)[len(lat) // 2], 2) if lat else None,
                                           "max": round(max(lat), 2) if lat else None, "n": len(lat)},
        "campaigns_without_result": [c["campaign"] for c in campaigns if c["outcome"] == "no-result-yet"],
        "rule_signals": {"single_server_speed_verdicts": [c["campaign"] for c in campaigns if c["single_server_speed_verdict"]],
                         "frozen_oracle_gates": [c["campaign"] for c in campaigns if c["frozen_oracle_gate"]]},
        "infra_event_files": sorted(infra, key=lambda x: -x["mentions"])[:10],
        "campaigns": campaigns,
    }
    if a.out:
        a.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    if a.markdown:
        lines = [f"# Efficiency metrics, last {a.days} days", "",
                 f"- commits: {len(commits)} ({dict(by_author)})",
                 f"- campaigns: {len(campaigns)}; prereg-to-result median {summary['prereg_to_result_latency_hours']['median']} h, max {summary['prereg_to_result_latency_hours']['max']} h",
                 f"- outcomes by lane: {summary['campaigns_by_lane_outcome']}",
                 f"- infra-event files: {len(infra)}",
                 f"- single-server speed verdicts: {summary['rule_signals']['single_server_speed_verdicts']}",
                 f"- frozen-oracle gates on changed kernels: {summary['rule_signals']['frozen_oracle_gates']}", ""]
        a.markdown.write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
