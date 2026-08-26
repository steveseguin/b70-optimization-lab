#!/usr/bin/env python3
"""Report-only audit for the TP1/MTP2 PIECEWISE sentinel's cache root.

The launch runner omitted its preregistered cache-isolation receipt and gate.
This script does not alter the cache, terminal receipt, or measured response. It
records the surviving dedicated cache tree and explicitly preserves that defect.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys


CAMPAIGN = "qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-20260826-r1"
ACK = f"AUDIT POSTRUN CACHE {CAMPAIGN}"
CACHE_ROOT = pathlib.Path(
    "/home/steve/qwen38-current-main-runs/"
    "cache-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-20260826-r1"
)
RAW_ROOT = pathlib.Path("/mnt/fast-ai/bench-results") / CAMPAIGN
TERMINAL = RAW_ROOT / "terminal-receipt.json"
MANIFEST_OUT = RAW_ROOT / "postrun-cache-files.sha256"
REPORT_OUT = RAW_ROOT / "postrun-cache-isolation-audit.json"
EXPECTED_LAUNCH_HEAD = "5dd48073b0c010bb94446a524bbc812eb68854db"
RANK_RE = re.compile(r"^rank_[0-9]+_[0-9]+$")


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(*, write: bool) -> dict[str, object]:
    if not CACHE_ROOT.is_dir():
        raise RuntimeError(f"missing dedicated cache root: {CACHE_ROOT}")
    if not TERMINAL.is_file():
        raise RuntimeError(f"missing terminal receipt: {TERMINAL}")
    if any(path.is_symlink() for path in CACHE_ROOT.rglob("*")):
        raise RuntimeError("cache root contains symlinks")

    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    terminal_ok = (
        terminal.get("terminal") is True
        and terminal.get("state") == "passed-quality-clean-sentinel"
        and terminal.get("launch_git_head") == EXPECTED_LAUNCH_HEAD
        and terminal.get("runner_return_code") == 0
    )

    entries: list[tuple[str, int, str]] = []
    rank_files: dict[str, list[str]] = {}
    shared_files: list[str] = []
    for path in sorted(item for item in CACHE_ROOT.rglob("*") if item.is_file()):
        rel = path.relative_to(CACHE_ROOT).as_posix()
        ranks = [part for part in pathlib.PurePosixPath(rel).parts if RANK_RE.match(part)]
        if len(ranks) > 1:
            raise RuntimeError(f"ambiguous rank namespace: {rel}")
        if ranks:
            rank_files.setdefault(ranks[0], []).append(rel)
        else:
            shared_files.append(rel)
        entries.append((rel, path.stat().st_size, sha256_file(path)))

    observed = sorted(rank_files)
    expected = ["rank_0_0"]
    manifest_text = "".join(
        f"{digest}  {size}  {rel}\n" for rel, size, digest in entries
    )
    manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
    passed = (
        terminal_ok
        and observed == expected
        and len(rank_files.get("rank_0_0", [])) > 0
        and len(entries) > 0
    )
    report: dict[str, object] = {
        "schema": "neural.download.postrun-cache-isolation-audit.v1",
        "campaign_id": CAMPAIGN,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat() if write else None,
        "audit_mode": "post-run-report-only",
        "posthoc": True,
        "original_terminal_enforced_cache_gate": False,
        "original_terminal_rewritten": False,
        "measured_response_rewritten": False,
        "cache_root": str(CACHE_ROOT),
        "terminal_receipt": str(TERMINAL),
        "terminal_receipt_sha256": sha256_file(TERMINAL),
        "launch_git_head": terminal.get("launch_git_head"),
        "terminal_identity_passed": terminal_ok,
        "expected_rank_namespaces": expected,
        "observed_rank_namespaces": observed,
        "rank_file_counts": {rank: len(rank_files.get(rank, [])) for rank in expected},
        "rank_files": rank_files.get("rank_0_0", []),
        "shared_file_count": len(shared_files),
        "total_file_count": len(entries),
        "total_bytes": sum(size for _, size, _ in entries),
        "content_manifest": str(MANIFEST_OUT),
        "content_manifest_sha256": manifest_sha256,
        "passed": passed,
        "authority": "Structural evidence for the surviving dedicated TP1 cache tree only; this audit does not retroactively change the original terminal class or authorize publication by itself.",
        "defect": "The launch runner promised cache isolation but emitted and enforced no cache-isolation receipt. This report preserves, rather than hides, that omission.",
    }

    if write:
        if MANIFEST_OUT.exists() or REPORT_OUT.exists():
            raise RuntimeError("post-run audit outputs already exist")
        MANIFEST_OUT.write_text(manifest_text, encoding="utf-8")
        REPORT_OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ack")
    args = parser.parse_args()
    if args.check == args.execute:
        parser.error("choose exactly one of --check or --execute")
    if args.execute and args.ack != ACK:
        parser.error(f"exact acknowledgement required: {ACK}")
    report = audit(write=args.execute)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
