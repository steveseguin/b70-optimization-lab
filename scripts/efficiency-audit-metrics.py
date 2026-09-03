#!/usr/bin/env python3
"""Objective lane-efficiency metrics from git history and committed campaign files.

Read-only. Works from any clone; needs no bench-results mount. Produces JSON
plus a markdown summary that the scheduled efficiency auditor (and humans)
reason from, so every audit measures the same things.

Metrics per window (default: last 7 days):
- commits by author class (codex / claude / other) and per day
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--markdown", type=Path)
    a = ap.parse_args()
    repo = a.repo
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=a.days)
    index_added_files(repo, since)

    # commits
    log = git(repo, "log", f"--since={since.isoformat()}", "--format=%H%x1f%cI%x1f%an%x1f%ae%x1f%s%x1f%b%x1e")
    commits = []
    for rec in log.split("\x1e"):
        if not rec.strip():
            continue
        h, ci, an, ae, subj, body = (rec.strip("\n").split("\x1f") + [""] * 6)[:6]
        commits.append({"hash": h[:9], "time": ci, "author": author_class(an, ae), "subject": subj,
                        "claude_attributed": "Co-Authored-By: Claude" in body})
    commits.sort(key=lambda c: c["time"])
    by_author = collections.Counter(c["author"] if not c["claude_attributed"] else "claude" for c in commits)
    per_day = collections.Counter(c["time"][:10] for c in commits)
    gaps = []
    for x, y in zip(commits, commits[1:]):
        gaps.append((dt.datetime.fromisoformat(y["time"]) - dt.datetime.fromisoformat(x["time"])).total_seconds() / 3600)
    long_gaps = sorted(gaps, reverse=True)[:5]

    # campaigns
    campaigns = []
    lanes = collections.defaultdict(lambda: collections.Counter())
    for prereg in sorted(repo.glob("experiments/*/data/*prereg*.json")):
        lane = prereg.parts[-3]
        t0 = first_commit_time(repo, str(prereg.relative_to(repo)))
        if not t0 or t0 < since:
            continue
        stem = re.sub(r"-?prereg.*$", "", prereg.name)
        results = [p for p in prereg.parent.glob(f"{stem}*result*.json")]
        res = results[0] if results else None
        t1 = first_commit_time(repo, str(res.relative_to(repo))) if res else None
        status = ""
        if res:
            try:
                d = json.loads(res.read_text())
                status = " ".join(str(d.get(k, "")) for k in ("status", "decision", "classification"))
            except Exception:
                status = "unreadable"
        oc = outcome(status) if res else "no-result-yet"
        text_blob = status
        campaigns.append({
            "lane": lane, "campaign": stem, "prereg_committed": t0.isoformat(),
            "result_committed": t1.isoformat() if t1 else None,
            "latency_hours": round((t1 - t0).total_seconds() / 3600, 2) if t1 else None,
            "outcome": oc,
            "single_server_speed_verdict": bool(SINGLE_SERVER_SPEED_RE.search(text_blob)),
            "frozen_oracle_gate": bool(FROZEN_ORACLE_RE.search(text_blob)),
        })
        lanes[lane][oc] += 1
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
    a.out.write_text(json.dumps(summary, indent=2) + "\n")
    if a.markdown:
        lines = [f"# Efficiency metrics, last {a.days} days", "",
                 f"- commits: {len(commits)} ({dict(by_author)})",
                 f"- campaigns: {len(campaigns)}; prereg-to-result median {summary['prereg_to_result_latency_hours']['median']} h, max {summary['prereg_to_result_latency_hours']['max']} h",
                 f"- outcomes by lane: {summary['campaigns_by_lane_outcome']}",
                 f"- infra-event files: {len(infra)}",
                 f"- single-server speed verdicts: {summary['rule_signals']['single_server_speed_verdicts']}",
                 f"- frozen-oracle gates on changed kernels: {summary['rule_signals']['frozen_oracle_gates']}", ""]
        a.markdown.write_text("\n".join(lines) + "\n")
    print(json.dumps({k: summary[k] for k in ("commits_total", "commits_by_author", "campaigns_total", "campaigns_by_lane_outcome", "prereg_to_result_latency_hours", "rule_signals")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
