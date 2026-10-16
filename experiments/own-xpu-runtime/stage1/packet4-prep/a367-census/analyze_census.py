#!/usr/bin/env python3
"""CPU-only A367 diagnostic device census. All durations are microseconds.

Usage: python3 -B analyze_census.py --manifest map.json --out-dir analysis

Mapping schema (a367-census-map-v1):
  {"schema":"a367-census-map-v1", "arm":"eager-census",
   "expected_ranks":[0,1,2,3], "auto_itt":true,
   "traces":[{"id":"r0","path":"unitrace.123.json","sha256":"...",
              "rank":0,"worker_pid":123,"rank_evidence":"rank-pids.json", "rank_evidence_sha256":"..."}],
   "steps":[], "family_rules":[], "graph_opaque":false}
Paths resolve relative to the manifest. SHA256 binds the raw bytes; worker_pid
and rank_evidence must come from the actual worker/rank receipt, never a GPU
synthetic PID. Only Chrome X events with cat=gpu_op are device work. Timing
units are Chrome microseconds even when displayTimeUnit says ns.

Normal segmentation uses ITT cpu_op X spans named
A367|verify|M=2|seq=N (optionally prefixed by one ITT domain::) or A367|draft|M=N|seq=N. A same-OS-process, same-thread
Flow_H2D_* source inside exactly one span links its id to gpu_op args.id.
The device timestamp need not fall inside the host span. Draft B=N markers
record batch_size only, never model M. Target markers are retained as
excluded_scopes (prefill or other target work) rather than counted as verify.
Requested-scope flow coverage and whole-trace assignment coverage are separate. Duplicate kernel IDs,
multiple sources or overlapping scopes are ambiguous and remain unassigned.
No timestamp-only host/device matching or repeat-pattern segmentation is used.

Optional explicit steps override auto assignment for their event references:
 {"id":"v0", "rank":0, "kind":"verify", "m":2,
  "event_refs":["r0:17"], "evidence":"audited correlation receipt"}
The index is the raw zero-based traceEvents (or root array) index. Empty steps
remain visible but incomplete. A device event cannot belong to two steps.
Optional family_rules [{"pattern":"regex", "family":"shared expert",
"evidence":"source dispatch + trace correlation"}] add audited rules. Conflicting
family matches remain unknown. Generic GEMMs/copies cannot establish a model
module merely from their name. Unassigned copies stay copies/memsets. Raw
trace files must be <=1 GiB each; larger files need offline trace sharding
with exact original indexes preserved via a new reviewed mapping. No traces
are modified. Do not run analysis alongside the server.

Completeness requires all requested ranks, verify and draft device steps on
all ranks, no opaque graph, and every device event assigned. Classification
coverage is separate: unknown family never becomes inferred model work.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

SCHEMA = "a367-census-map-v1"
DESIGN = "notes/2026-10-16-flash-next-m2-glue-fusion-design.md#dispatch-audit-avoid-counting-work-that-is-absent"
FAMILIES = ("routed MoE GEMM", "MoE glue", "shared expert", "collectives/all-reduce",
            "QSA", "GDN", "HC", "PLE", "LM head/sampler", "MTP draft",
            "copies/memsets", "unknown")
# Only distinct source names identify a family; generic GEMMs/pointwise kernels
# need an explicit audited rule. No timing-based classification.
BUILTINS = (
    (r"\b(?:moe_gemm|fused_moe_kernel|_fused_moe_kernel)\b", "routed MoE GEMM"),
    (r"\b(?:moe_align\w*|moe_sum|expert_map\w*|silu_and_mul_per_block_quant)\b", "MoE glue"),
    (r"\b(?:allreduce\w*|all_reduce\w*|twoshots\w*|reduce_scatter\w*)\b", "collectives/all-reduce"),
    (r"\b(?:qsa_\w*|\w+_qsa\w*)\b", "QSA"),
    (r"\b(?:gdn_\w*|\w+_gdn\w*)\b", "GDN"),
    (r"\b(?:hc_\w*)\b", "HC"),
    (r"\b(?:ple_\w*)\b", "PLE"),
    (r"\b(?:lm_head\w*|sampling_from_probs\w*|sample_top_p\w*)\b", "LM head/sampler"),
    (r"(?:zeCommandListAppend(?:MemoryCopy|MemoryFill|ImageCopy)|\bmemcpy\b|\bmemset\b)", "copies/memsets"),
)
BOUNDARIES = {
    "routed MoE GEMM": "Retain both tuned GEMMs, FP8 scales, W2 BF16 cast and reduction ownership; these are real arithmetic, not removable glue (audit 1, 3, 4).",
    "MoE glue": "Preserve sorted IDs/sentinels, remote -1 experts, native quantization and sum tree. Map lookup may enter both GEMM consumers; routed SiLU/quant is already fused (audit 1-4).",
    "shared expert": "Keep native sigmoid and every BF16 materialization; combine shared+routed before the late TP reduction (audit 5).",
    "collectives/all-reduce": "Retain two one-row reductions, payload/dtype/communicator/order. Coalesce only surrounding byte copies; a two-row reduction changes arithmetic (audit 5; design patch 01).",
    "QSA": "Keep stable sort, attention index order, norm/rotary math and fallback. Fuse only proven integer cast/mask/expansion consumers (audit 7; design patch 03).",
    "GDN": "Retain exact serial recurrence, scratch, completion barrier and rollback/state stores; prove writes dominate reads before deleting zeros (source census GDN rows).",
    "HC": "Already fused; preserve BF16 store/reload and fixed norm reduction hierarchy (audit 6).",
    "PLE": "Preserve compressed-weight interpretation, rollback and cache state; do not combine conditional branches into fictitious work (audit 8; source census PLE rows).",
    "LM head/sampler": "Outside target forward; preserve logits, seed and target verification. Never charge sampling to target glue (source census final row).",
    "MTP draft": "Outside target forward; preserve draft arithmetic, acceptance and unchanged target verification (source census final row).",
    "copies/memsets": "Prove producer/consumer lifetime, graph addresses and dtype/stride. Views and already-satisfied casts are not launches; preserve state/rollback stores (audit 8).",
    "unknown": "No fusion claim until source dispatch and producer/consumer boundaries are identified; opaque native sub-kernels remain unknown (audit 1-8).",
}
SCOPE = re.compile(r"^(?:[^:|\r\n]+::)?A367\|(verify|draft|target)\|(M|B)=([1-9][0-9]*)\|seq=([0-9]+)$")


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"invalid finite number: {label}")
    return float(value)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def interval_stats(rows):
    """Sum counts overlaps; busy is union on this rank, idle is internal gaps."""
    if not rows:
        return {"kernel_count": 0, "device_event_count": 0, "copy_memset_count": 0, "sum_device_us": 0.0, "busy_union_us": 0.0,
                "wall_span_us": 0.0, "idle_us": 0.0, "idle_gaps_us": [],
                "start_us": None, "end_us": None}
    spans = sorted((r["ts_us"], r["ts_us"] + r["duration_us"]) for r in rows)
    start, end = spans[0]
    busy = 0.0
    gaps = []
    for left, right in spans[1:]:
        if left > end:
            busy += end - start
            gaps.append(left - end)
            start, end = left, right
        else:
            end = max(end, right)
    busy += end - start
    wall = max(right for _, right in spans) - spans[0][0]
    return {"kernel_count": sum(r.get("intrinsic_family", r.get("family")) != "copies/memsets" for r in rows),
            "device_event_count": len(rows),
            "copy_memset_count": sum(r.get("intrinsic_family", r.get("family")) == "copies/memsets" for r in rows),
            "sum_device_us": sum(r["duration_us"] for r in rows),
            "busy_union_us": busy, "wall_span_us": wall, "idle_us": sum(gaps),
            "idle_gaps_us": gaps, "start_us": spans[0][0],
            "end_us": max(right for _, right in spans)}


def classify(name, rules):
    found = {family for pattern, family in rules if pattern.search(name)}
    return next(iter(found)) if len(found) == 1 else "unknown"


def grouped(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return sorted(({"name": name, **interval_stats(items)} for name, items in groups.items()),
                  key=lambda r: (-r["sum_device_us"], r["name"]))


def auto_steps(events, trace, devices):
    """Return explicit mappings via host ITT scope -> H2D flow -> device ID."""
    scopes = []
    for index, event in enumerate(events):
        match = SCOPE.fullmatch(str(event.get("name", "")))
        if not match or event.get("ph") != "X" or event.get("cat") != "cpu_op":
            continue
        if event.get("pid") != trace["worker_pid"]:
            continue
        start = number(event.get("ts"), "scope ts")
        duration = number(event.get("dur"), "scope duration")
        if duration < 0:
            raise ValueError("negative scope duration")
        kind, dimension, m, seq = match.groups()
        if dimension == "B" and kind != "draft":
            continue
        if kind == "verify" and int(m) != 2:
            continue  # M=1/prefill is not an M=2 verify census.
        scopes.append({"id": f"{trace['id']}:scope:{index}", "rank": trace["rank"],
                       "kind": kind, "m": int(m) if dimension == "M" else None,
                       "batch_size": int(m) if dimension == "B" else None, "sequence": int(seq),
                       "host_flow_sources": 0, "unresolved_flow_sources": 0,
                       "event_refs": [], "evidence": f"ITT event {trace['id']}:{index}; same-thread H2D flow id -> gpu_op args.id",
                       "tid": event.get("tid"), "start": start, "end": start + duration})
    sources = defaultdict(list)
    for event in events:
        if event.get("ph") == "s" and str(event.get("cat", "")).startswith("Flow_H2D_"):
            if event.get("pid") == trace["worker_pid"]:
                sources[str(event.get("id"))].append(event)
    device_ids = Counter(str(r["correlation_id"]) for r in devices if r["correlation_id"] is not None)
    for source_list in sources.values():
        for source in source_list:
            ts = number(source.get("ts"), "flow ts")
            for scope in scopes:
                if source.get("tid") == scope["tid"] and scope["start"] <= ts < scope["end"]:
                    scope["host_flow_sources"] += 1
    for row in devices:
        kid = row["correlation_id"]
        if kid is None or device_ids[str(kid)] != 1 or len(sources[str(kid)]) != 1:
            continue
        source = sources[str(kid)][0]
        ts = number(source.get("ts"), "flow ts")
        matches = [s for s in scopes if source.get("tid") == s["tid"] and s["start"] <= ts < s["end"]]
        if len(matches) == 1:
            matches[0]["event_refs"].append(row["event_ref"])
    for scope in scopes:
        scope["unresolved_flow_sources"] = scope["host_flow_sources"] - len(scope["event_refs"])
    return [{k: v for k, v in s.items() if k not in {"tid", "start", "end"}} for s in scopes]


def clusters(rows, threshold=50.0, max_gap=10.0):
    """Contiguous small events within a step; observed clusters, not savings."""
    result, current = [], []
    def flush():
        if len(current) >= 2:
            families = sorted({r["family"] for r in current})
            result.append({**interval_stats(current), "event_refs": [r["event_ref"] for r in current],
                           "families": families, "fusion_candidate": "requires boundary proof",
                           "exact_preserving_boundaries": {f: BOUNDARIES[f] for f in families},
                           "dispatch_audit": DESIGN})
        current.clear()
    for row in sorted(rows, key=lambda r: (r["ts_us"], r["event_ref"])):
        if row["duration_us"] >= threshold:
            flush()
            continue
        if current and row["ts_us"] - max(r["ts_us"] + r["duration_us"] for r in current) > max_gap:
            flush()
        current.append(row)
    flush()
    return sorted(result, key=lambda r: -r["sum_device_us"])


def analyze(manifest_path):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != SCHEMA:
        raise ValueError("wrong manifest schema")
    if manifest.get("arm") not in {"eager-census", "graph-census", "graph-reference"}:
        raise ValueError("unknown arm")
    if "identity" in manifest or "lifecycle" in manifest:
        for key in ("identity", "lifecycle"):
            record = manifest[key]
            path = manifest_path.parent / record["path"]
            if sha(path) != record["sha256"]:
                raise ValueError(f"{key} hash mismatch")
        identity = json.loads((manifest_path.parent / manifest["identity"]["path"]).read_text())
        lifecycle = json.loads((manifest_path.parent / manifest["lifecycle"]["path"]).read_text())
        if (identity.get("arm") != manifest["arm"] or lifecycle.get("identity_sha256") != manifest["identity"]["sha256"]
                or lifecycle.get("clean_exit") is not True or lifecycle.get("gap_complete") is not True):
            raise ValueError("manifest arm/identity/lifecycle mismatch")
    expected = manifest.get("expected_ranks", [0, 1, 2, 3])
    if not expected or len(set(expected)) != len(expected) or any(type(r) is not int or r < 0 for r in expected):
        raise ValueError("invalid expected ranks")
    rules = [(re.compile(p, re.I), f) for p, f in BUILTINS]
    for rule in manifest.get("family_rules", []):
        if rule["family"] not in FAMILIES or not rule.get("evidence"):
            raise ValueError("family rule needs supported family and evidence")
        rules.append((re.compile(rule["pattern"], re.I), rule["family"]))
    rows, step_maps, trace_receipts, ids, bindings = [], [], [], set(), {}
    for trace in manifest.get("traces", []):
        if trace["id"] in ids or ":" in trace["id"]:
            raise ValueError("duplicate trace id or colon in trace id")
        ids.add(trace["id"])
        rank = trace["rank"]
        if rank not in expected or type(trace.get("worker_pid")) is not int or trace["worker_pid"] <= 0 or not trace.get("rank_evidence"):
            raise ValueError("trace requires expected rank, positive OS worker_pid and rank evidence")
        pid = trace["worker_pid"]
        if pid in bindings and bindings[pid] != rank:
            raise ValueError("one worker PID assigned multiple ranks")
        bindings[pid] = rank
        evidence_path = manifest_path.parent / trace["rank_evidence"]
        if sha(evidence_path) != trace.get("rank_evidence_sha256"):
            raise ValueError("rank evidence hash mismatch")
        evidence = json.loads(evidence_path.read_text())
        if (evidence.get("schema") != "a367-census-marker-rank-v1"
                or evidence.get("rank") != rank or evidence.get("pid") != pid):
            raise ValueError("rank evidence binding mismatch")
        path = manifest_path.parent / trace["path"]
        if path.stat().st_size > 1024 * 1024 * 1024:
            raise ValueError("trace exceeds 1 GiB offline parser limit")
        digest = sha(path)
        if digest != trace.get("sha256"):
            raise ValueError(f"trace hash mismatch: {trace['id']}")
        payload = json.loads(path.read_text())
        events = payload.get("traceEvents") if isinstance(payload, dict) else payload
        if not isinstance(events, list) or any(not isinstance(e, dict) for e in events):
            raise ValueError("not a Chrome trace event array")
        if isinstance(payload, dict) and payload.get("timestampUnit", "us") != "us":
            raise ValueError("only Chrome microsecond timestamps supported")
        devices = []
        for index, event in enumerate(events):
            if event.get("ph") != "X" or event.get("cat") != "gpu_op":
                continue
            start = number(event.get("ts"), "device ts")
            duration = number(event.get("dur"), "device duration")
            if duration < 0:
                raise ValueError("negative device duration")
            name = str(event.get("name", ""))
            devices.append({"event_ref": f"{trace['id']}:{index}", "rank": rank,
                            "name": name, "ts_us": start, "duration_us": duration,
                            "family": classify(name, rules), "step_id": None,
                            "device_pid": event.get("pid"), "device_tid": event.get("tid"),
                            "correlation_id": event.get("args", {}).get("id")})
        rows.extend(devices)
        if manifest.get("auto_itt", True):
            step_maps.extend(auto_steps(events, trace, devices))
        trace_receipts.append({"id": trace["id"], "path": str(path), "sha256": digest,
                               "bytes": path.stat().st_size, "rank": rank, "worker_pid": pid,
                               "rank_evidence": trace["rank_evidence"], "rank_evidence_sha256": trace["rank_evidence_sha256"], "device_events": len(devices)})
    # Explicit entries replace auto membership for those events, but never each other.
    explicit = manifest.get("steps", [])
    explicit_refs = [ref for s in explicit for ref in s.get("event_refs", [])]
    if len(set(explicit_refs)) != len(explicit_refs):
        raise ValueError("device event assigned to multiple explicit steps")
    explicit_set = set(explicit_refs)
    for s in step_maps:
        s["event_refs"] = [ref for ref in s["event_refs"] if ref not in explicit_set]
    step_maps.extend(explicit)
    by_ref = {r["event_ref"]: r for r in rows}
    steps, excluded_scopes, step_ids = [], [], set()
    for step in step_maps:
        if step["id"] in step_ids:
            raise ValueError("duplicate step id")
        step_ids.add(step["id"])
        if step["rank"] not in expected or step.get("kind") not in {"verify", "draft", "target"} or not step.get("evidence"):
            raise ValueError("step requires expected rank, verify/draft kind and evidence")
        valid_m = type(step.get("m")) is int and step["m"] > 0
        valid_batch = step["kind"] == "draft" and step.get("m") is None and type(step.get("batch_size")) is int and step["batch_size"] > 0
        if not (valid_m or valid_batch) or (step["kind"] == "verify" and step["m"] != 2):
            raise ValueError("verify step must be M=2; draft M positive")
        selected = []
        for ref in step.get("event_refs", []):
            if ref not in by_ref:
                raise ValueError(f"step references absent/non-device event: {ref}")
            row = by_ref[ref]
            if row["rank"] != step["rank"] or row["step_id"] is not None:
                raise ValueError("step rank mismatch or duplicate event membership")
            row["step_id"] = step["id"]
            row["scope_kind"] = step["kind"]
            row["intrinsic_family"] = row["family"]
            if step["kind"] == "draft":
                row["family"] = "MTP draft"
            selected.append(row)
        destination = excluded_scopes if step["kind"] == "target" else steps
        destination.append({**step, **interval_stats(selected), "families": grouped(selected, "family"),
                            "small_kernel_clusters": clusters(selected)})
    rank_rows = []
    for rank in expected:
        selected = [r for r in rows if r["rank"] == rank]
        assigned = [r for r in selected if r["step_id"] is not None]
        kinds = Counter(s["kind"] for s in steps if s["rank"] == rank and s["device_event_count"])
        rank_rows.append({"rank": rank, **interval_stats(selected), "assigned_kernels": len(assigned),
                          "unassigned_kernels": len(selected) - len(assigned),
                          "verify_steps": kinds["verify"], "draft_steps": kinds["draft"],
                          "family_classified_kernels": sum(r["family"] != "unknown" for r in selected),
                          "families": grouped(selected, "family")})
    issues = []
    requested_complete = bool(steps) and not manifest.get("graph_opaque")
    for step in steps:
        if not step["device_event_count"] or step.get("unresolved_flow_sources", 0):
            requested_complete = False
            issues.append(f"{step['id']}: empty or unresolved requested-scope flow coverage")
    unbound_device_traces = sum(t.get("device_events", 0) for t in manifest.get("excluded_traces", []))
    if unbound_device_traces:
        issues.append(f"{unbound_device_traces} device events in unbound excluded traces")
        requested_complete = False
    if manifest.get("graph_opaque"):
        issues.append("graph replay is opaque: no graph-internal attribution claim")
    for row in rank_rows:
        if not row["device_event_count"]:
            issues.append(f"rank {row['rank']}: no device timestamps")
        if not row["verify_steps"] or not row["draft_steps"]:
            requested_complete = False
            issues.append(f"rank {row['rank']}: missing correlated verify or draft steps")
        if row["unassigned_kernels"]:
            issues.append(f"rank {row['rank']}: {row['unassigned_kernels']} device events unassigned")
    if any(not s["device_event_count"] for s in steps):
        issues.append("one or more declared scopes contain no correlated device events")
    candidate_clusters = [{"rank": s["rank"], "step_id": s["id"], "kind": s["kind"], **c}
                          for s in steps for c in s["small_kernel_clusters"]]
    candidate_clusters.sort(key=lambda c: -c["sum_device_us"])
    sinks = grouped(rows, "name")
    for sink in sinks:
        families = sorted({r["family"] for r in rows if r["name"] == sink["name"]})
        sink["families"] = families
        sink["exact_preserving_boundaries"] = {f: BOUNDARIES[f] for f in families}
        sink["dispatch_audit"] = DESIGN
        # Cross-rank timestamp unions are not meaningful: retain only sum/count.
        for key in ("busy_union_us", "wall_span_us", "idle_us", "idle_gaps_us", "start_us", "end_us"):
            sink.pop(key)
    return {"schema": "a367-device-census-v1", "diagnostic_only": True, "speed_claim": False,
            "arm": manifest["arm"], "timing_unit": "us", "manifest_sha256": sha(manifest_path),
            "segmentation_complete": not issues, "requested_scope_flow_coverage_complete": requested_complete,
            "whole_trace_assignment_complete": bool(rows) and not unbound_device_traces and all(r["step_id"] for r in rows),
            "excluded_scopes": excluded_scopes, "issues": issues, "traces": trace_receipts,
            "rank_summaries": rank_rows, "excluded_traces": manifest.get("excluded_traces", []), "steps": steps, "timeline": sorted(rows, key=lambda r: (r["rank"], r["ts_us"], r["event_ref"])),
            "ranked_time_sinks": sinks, "ranked_small_kernel_clusters": candidate_clusters,
            "family_boundaries": BOUNDARIES, "dispatch_audit": DESIGN,
            "interpretation": "Device event counts include copies/memsets; kernel counts exclude positively identified copies/memsets (unclassified gpu_op names remain unknown kernel candidates). Sum includes overlapping device work. Busy/idle use the union within a rank/step; idle excludes edges before first/after last event. Inter-step wait is not step idle. Cross-rank sums are device work, not latency or projected savings. Unknown families remain unknown; clusters are candidates requiring boundary proof."}


def markdown(result):
    lines = ["# A367 diagnostic device census", "", f"Arm: `{result['arm']}`. Diagnostic only; no speed claim.", "",
             f"Segmentation complete: **{str(result['segmentation_complete']).lower()}**. Requested-scope flow coverage complete: **{str(result['requested_scope_flow_coverage_complete']).lower()}**.", "", result["interpretation"], "",
             "| Rank | Device events | Unassigned | Verify steps | Draft steps | Sum device µs |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in result["rank_summaries"]:
        lines.append(f"| {row['rank']} | {row['device_event_count']} | {row['unassigned_kernels']} | {row['verify_steps']} | {row['draft_steps']} | {row['sum_device_us']:.3f} |")
    if result["issues"]:
        lines += ["", "Incomplete evidence:", ""] + ["- " + issue for issue in result["issues"]]
    lines += ["", "Largest device-work totals (all ranks, not latency):", ""]
    for sink in result["ranked_time_sinks"][:10]:
        safe_name = sink['name'].replace('`', "'").replace('\n', ' ')
        lines.append(f"- `{safe_name}`: {sink['sum_device_us']:.3f} µs / {sink['device_event_count']} events ({', '.join(sink['families'])}).")
        for note in sink["exact_preserving_boundaries"].values():
            lines.append(f"  Boundary: {note}")
    lines += ["", "Largest observed clusters of kernels below 50 µs (gaps ≤10 µs):", ""]
    for cluster in result["ranked_small_kernel_clusters"][:5]:
        lines.append(f"- Rank {cluster['rank']}, `{cluster['step_id']}`: {cluster['device_event_count']} events, {cluster['sum_device_us']:.3f} µs summed, {cluster['wall_span_us']:.3f} µs span; boundary proof required.")
        for note in cluster["exact_preserving_boundaries"].values():
            lines.append(f"  Boundary: {note}")
    lines += ["", f"Dispatch audit: `{DESIGN}`. Full per-step metrics, event references, family coverage and boundary notes are in `census.json`.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    result = analyze(args.manifest)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    targets = [args.out_dir / "census.json", args.out_dir / "census.md"]
    if any(p.exists() for p in targets):
        parser.error("refusing to overwrite census output")
    targets[0].write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    targets[1].write_text(markdown(result))
    print(json.dumps({"segmentation_complete": result["segmentation_complete"], "issues": result["issues"], "out_dir": str(args.out_dir)}))
    return 0  # Missing coverage is a diagnostic finding, recorded prominently.


if __name__ == "__main__":
    raise SystemExit(main())
