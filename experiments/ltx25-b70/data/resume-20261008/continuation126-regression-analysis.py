#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Read-only CPU receipt analysis. Writes only its new analysis JSON beside this file.

No device/runtime import. No process, socket or live-server access. The optional
metadata replay reads archived regular evidence only, under the current directory
layout; it is not a reconstruction of historical walk duration.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import time
from datetime import datetime, timezone

os.environ["OMP_NUM_THREADS"] = "2"
HERE = Path(__file__).resolve().parent
LANE = HERE.parent.parent
ROOT = Path("/mnt/fast-ai/bench-results/ltx25-baseline-20260913")
SESSIONS = ("s121-live01", "s121-live02", "s123b-legacy-live01", "s123b-live01", "s123b-live02")
SOURCES = {}

def pin(path):
    raw = path.read_bytes()
    SOURCES[str(path)] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return raw

def read(path, lines=False):
    raw = pin(path)
    return [json.loads(x) for x in raw.splitlines() if x.strip()] if lines else json.loads(raw)

def stats(values):
    values = sorted(x for x in values if x is not None)
    if not values:
        return None
    return {"n": len(values), "median": statistics.median(values),
            "mean": statistics.mean(values), "min": values[0], "max": values[-1]}

def diff(t, a, b):
    return (t[b] - t[a]) / 1e9

def summarize(rows):
    keys = [k for k, v in rows[0].items() if isinstance(v, (int, float)) and k != "seq"]
    return {group: {k: stats([row[k] for row in selected]) for k in keys}
            for group, selected in (("all", rows), ("even_source", [r for r in rows if r["seq"] % 2 == 0]),
                                    ("odd_source", [r for r in rows if r["seq"] % 2 == 1]))}

def collect(session):
    manifest = read(Path("/home/steve/ltx-stream") / session / "manifest.jsonl", True)
    packet = "121" if session.startswith("s121") else "123b"
    first = manifest[0]
    matches = []
    for root in ROOT.glob("encoder-server-continuation-stream-" + packet + "*"):
        path = root / "receipts" / ("receipt-" + first["run_name"] + ".json")
        if path.is_file() and json.loads(path.read_bytes())["server_identity_sha256"] == first["server_identity_sha256"]:
            matches.append(root)
    assert len(matches) == 1, (session, matches)
    root = matches[0]
    tables = {kind: {x["stream_seq"]: read(root / "receipts" / (kind + "-" + x["run_name"] + ".json"))
                     for x in manifest} for kind in ("receipt", "decode", "preview")}
    receipts, decodes, previews = [tables[k] for k in ("receipt", "decode", "preview")]
    rows = []
    for seq in sorted(receipts):
        if seq < 10 or seq + 1 not in receipts:
            continue
        r, d, v, nxt = receipts[seq], decodes[seq], previews[seq], receipts[seq + 1]
        t, dt = r["timing_ns"], d["timing_ns"]
        marks = nxt["turnaround"]["marks_ns"]
        snapshots = {x["label"]: x for x in r["snapshots"]}
        row = {"seq": seq, "period": (nxt["timing_ns"]["submit"] - t["submit"]) / 1e9,
               "submit_to_a": diff(t, "submit", "sampler_a_start"),
               "sampler_a": diff(t, "sampler_a_start", "stage_a_done"),
               "upsample_bprep": diff(t, "stage_a_done", "sampler_b_start"),
               "sampler_b": diff(t, "sampler_b_start", "stage_b_done"),
               "b_done_to_anchor": diff(t, "stage_b_done", "anchor_ready"),
               "anchor_to_receipt": diff(t, "anchor_ready", "receipt_staged"),
               "receipt_to_next": (nxt["timing_ns"]["submit"] - t["receipt_staged"]) / 1e9,
               "commit_to_first_served": diff(marks, "commit_written", "first_served"),
               "staged_to_commit": diff(marks, "receipt_staged", "commit"),
               "commit_write": diff(marks, "commit", "commit_written"),
               "commit_to_executor_exit": diff(marks, "commit_written", "executor_exit"),
               "served_to_submit": diff(marks, "first_served", "submit"),
               "snapshot_inner_before": diff(snapshots["request-before"], "start_ns", "end_ns"),
               "snapshot_inner_after": diff(snapshots["request-after"], "start_ns", "end_ns"),
               "status_calls": r["authority_checks"]["status_route_calls"],
               "status_s": r["authority_checks"]["status_route_s"],
               "healthy_calls": r["authority_checks"]["healthy_calls"],
               "healthy_s": r["authority_checks"]["healthy_s"],
               "plan_digest_s": r["authority_checks"]["plan_digest_s"],
               "prior_preview_lead_to_receipt": (t["receipt_staged"] - previews[seq-1]["timing_ns"]["preview_written"]) / 1e9,
               "prior_preview_lead_to_decode": (dt["decode_start"] - previews[seq-1]["timing_ns"]["preview_written"]) / 1e9,
               "precompute_a": diff(dt, "precompute_a_start", "precompute_a_done"),
               "preview_queue_wait": v["timing_s"]["queue_wait"],
               "preview_write": v["timing_s"]["write"],
               "preview_copy_enqueue": (v["timing_ns"]["preview_queued"] - v["timing_ns"]["record_written"]) / 1e9,
               "anchor_decode_equal": d["anchor_decode"]["equal"],
               "timeline_ns": {"request": t, "next_turnaround": marks, "decode": dt,
                               "preview": v["timing_ns"], "snapshots": {k: {z: x[z] for z in ("start_ns", "end_ns")} for k,x in snapshots.items()}}}
        row.update({"submit_" + k: value for k, value in r["timing_s"]["submit_split"].items()})
        row.update({"a_split_" + k: value for k, value in r["timing_s"]["sampler_a_split"].items()})
        row.update({"decode_" + k: value for k, value in d["timing_s"].items()})
        assert abs(sum(row[k] for k in ("submit_to_a", "sampler_a", "upsample_bprep", "sampler_b", "b_done_to_anchor", "anchor_to_receipt", "receipt_to_next")) - row["period"]) < 1e-7
        if seq not in (10, 11, 12, 13):
            del row["timeline_ns"]
        rows.append(row)
    destination_periods = [{"seq": seq, "period": (r["timing_ns"]["submit"] - receipts[seq-1]["timing_ns"]["submit"]) / 1e9}
                           for seq,r in receipts.items() if seq >= 10]
    return {"root": str(root), "identity": first["server_identity_sha256"], "manifest_rows": len(manifest),
            "actual_server_options": receipts[10]["server_options"], "source_seq_convention": "period begins at seq; destination parity is reversed",
            "full": summarize(rows), "fixed40": summarize([r for r in rows if r["seq"] < 50]),
            "fixed30": summarize([r for r in rows if r["seq"] < 40]),
            "destination_all_available": summarize(destination_periods), "rows": rows}

runs = {session: collect(session) for session in SESSIONS}
for packet in ("121", "123b", "125"):
    for relative in ("source/main.py", "source/scripts/integration.py", "source/scripts/stream_preview.py", "source/scripts/ltx_resolution_session.py", "source/comfy/model_management.py"):
        pin(ROOT / ("prepared-continuation-stream-" + packet) / relative)
for relative in ("run_storage.py", "residency123.py"):
    pin(ROOT / "prepared-continuation-stream-123b/source/scripts" / relative)
pin(ROOT / "prepared-continuation-stream-123b/source/comfy_extras/nodes_lt_upsampler.py")
# Bounded metadata-only replay under the current archived layout, never a live request.
path = ROOT / "prepared-continuation-stream-123b/source/scripts/run_storage.py"
spec = importlib.util.spec_from_file_location("continuation126_archived_storage", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
account = module.OwnWrites(ROOT, Path(runs["s123b-legacy-live01"]["root"]), "stream123b")
samples = []
for index in range(9):
    started = time.monotonic_ns()
    consumed = account.allocated_bytes()
    samples.append((time.monotonic_ns() - started) / 1e9)
plan_replay = {}
for packet in ("121", "123b"):
    envelope = read(ROOT / ("prepared-continuation-stream-" + packet) / "resolution/stream-plan.json")
    plan = envelope["plan"]
    samples_plan = []
    for repeat in range(35):
        started = time.monotonic_ns()
        raw = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        digest = hashlib.sha256(raw).hexdigest()
        samples_plan.append((time.monotonic_ns() - started) / 1e9)
        assert digest == envelope["plan_sha256"]
    plan_replay[packet] = {"canonical_bytes": len(raw), "digest": digest, "samples_s": samples_plan, "summary": stats(samples_plan), "total_35_s": sum(samples_plan)}
result = {"schema": "ltx.continuation126.regression-analysis.v1", "observed_utc": datetime.now(timezone.utc).isoformat(),
          "runs": runs, "sources": SOURCES, "plan_replay": plan_replay,
          "scan_replay": {"samples_s": samples, "warm": stats(samples[1:]), "allocated_bytes": consumed,
                          "recorded_paths": len(account._blocks), "cached_dirs": len(account._dirs),
                          "limitation": "Post-archive scope excludes moved stream output/requests; replay cannot identify historical scan time or lock wait."},
          "structural_checks": {"sessions": len(runs), "all_chain_buckets_sum": True,
                                "all_saved_cone_equal": all(r["anchor_decode_equal"] for run in runs.values() for r in run["rows"])}}
assert result["structural_checks"]["all_saved_cone_equal"]
pin(Path(__file__))
(HERE / "continuation126-regression-evidence.json").write_text(json.dumps(result, indent=2) + "\n")
for session, run in runs.items():
    print(session, "full", run["full"]["all"]["period"], "fixed40", run["fixed40"]["all"]["period"])
print("scan replay", result["scan_replay"])
