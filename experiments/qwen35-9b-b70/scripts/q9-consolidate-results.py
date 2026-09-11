#!/usr/bin/env python3
"""Consolidate every 2026-09-09 Qwen3.5-9B arm into one machine-readable record.

Reads each campaign root directly rather than any hand-maintained table, so the summary cannot
drift from the evidence. Arms that aborted are included with their reason: a campaign's negative
and blocked results are part of its output, not omissions from it.

usage: q9-consolidate-results.py [--out FILE]
"""
from __future__ import annotations

import argparse, json, re
from pathlib import Path

BENCH = Path("/mnt/fast-ai/bench-results")
GATE_RE = re.compile(r"(G[123])[^:]*: (\d+)/(\d+)")
PERF_RE = re.compile(r"(\S+): class_balanced_median_tok_s=([0-9.]+)")


def read_arm(root: Path) -> dict:
    log = root / "campaign.log"
    text = log.read_text(errors="replace") if log.is_file() else ""
    cfg = (root / "config.txt").read_text().strip() if (root / "config.txt").is_file() else ""
    depth = re.search(r"DEPTH=(\d+)", cfg)
    out = {
        "arm": root.name.rsplit("-", 1)[-1],
        "root": root.name,
        "depth": int(depth.group(1)) if depth else None,
        "aborted": (root / "ABORTED").is_file(),
        "abort_reason": (root / "ABORTED").read_text().strip() if (root / "ABORTED").is_file() else None,
        "config": cfg,
        "gates": {g: f"{a}/{b}" for g, a, b in GATE_RE.findall(text)},
        "strict_tok_s": {k: float(v) for k, v in PERF_RE.findall(text)},
        "ladders": {},
    }
    for lad in sorted(root.glob("*/ladder.json")):
        try:
            d = json.loads(lad.read_text())
        except Exception:
            continue
        rungs = {}
        for b in d.get("batches", []):
            r = rungs.setdefault(b["concurrency"], {"passes": [], "divergent": 0, "requests": 0})
            r["passes"].append(round(b.get("aggregate_tok_s_wall") or 0, 1))
            r["divergent"] += b["oracle_exact_total"] - b["oracle_exact_count"]
            r["requests"] += b["oracle_exact_total"]
        out["ladders"][lad.parent.name] = {
            "identity_qualified": (d.get("identity_qualification") or {}).get(
                "complete_outputs_exact_vs_sequential_oracle"),
            "rungs": rungs,
        }
    for dep in sorted(root.glob("*/depth.stdout")):
        try:
            t = dep.read_text(); d = json.loads(t[t.find("{"):t.rfind("}") + 1])
        except Exception:
            continue
        out.setdefault("context", {})[dep.parent.name] = {
            "status": d.get("status"),
            "points": [
                {"context": p["active_context_tokens"], "tok_s": round(p["median_decode_tok_s"], 3),
                 "ttft_ms": round(p["median_ttft_ms"]), "gates": p["all_request_gates_passed"],
                 "exact_vs_oracle": p["all_target_oracle_exact"]}
                for p in d.get("points", [])
            ],
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="experiments/qwen35-9b-b70/data/2026-09-09-q9-campaign-consolidated.json")
    args = ap.parse_args()
    arms = [read_arm(p) for p in sorted(BENCH.glob("qwen35-9b-w4a16-*-20260909-*")) if p.is_dir()]
    superseded = [a for a in arms if any(t in a["root"] for t in ("failed", "invalid", "aborted"))]
    ran = [a for a in arms if a not in superseded]
    completed = [a for a in ran if not a["aborted"]]
    blocked = [a for a in ran if a["aborted"]]
    doc = {
        "schema": "b70-lab.campaign-consolidated.v1",
        "campaign": "qwen35-9b-w4a16-tp1-20260909",
        "host": "steve-b70s (4x Intel Arc Pro B70 32 GiB, 125.7 GiB RAM)",
        "model": "RedHatAI/Qwen3.5-9B-quantized.w4a16 @ a398088c4228b0ae0c8c78df88fd1e4bf445f068",
        "runtime": "R276 sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad",
        "note": ("All arms TP1, serial on card 0. Non-zero cards cannot host a server on this stack "
                 "(shared launcher sets ZE_AFFINITY_MASK and ONEAPI_DEVICE_SELECTOR from one value). "
                 "Aggregate figures are scoped capacity evidence, never single-user headlines."),
        "arm_count": {"total": len(arms), "completed": len(completed),
                      "blocked": len(blocked), "superseded": len(superseded)},
        "arms": arms,
    }
    p = Path(args.out); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    print(f"wrote {p} - {len(completed)} completed, {len(blocked)} blocked, "
          f"{len(superseded)} superseded, {len(arms)} roots")
    for a in blocked:
        print(f"  BLOCKED {a['arm']:<9} {(a['abort_reason'] or '')[:70]}")
    for a in completed:
        g = ",".join(f"{k}={v}" for k, v in sorted(a["gates"].items())) or "-"
        best = max(a["strict_tok_s"].values(), default=None)
        print(f"  {a['arm']:<9} depth={a['depth']} gates[{g}] best_strict={best}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
