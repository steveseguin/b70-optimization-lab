#!/usr/bin/env python3
"""CPU-only evidence synthesis. No runtime imports, model reads or device calls.

--capture freezes small local receipts once; --check reproduces the report.
Run with nice19, taskset 8-15,24-31, python3 -B and stdin /dev/null.
"""
import argparse
import ast
import base64
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import resource
import statistics as st
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = HERE.parent
ARCHIVE = STAGE / "packet124c-record-bundle/submission/prepared-a/evidence.json.gz"
METHOD = STAGE / "packet126-early-draft/method/p85_model.py"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(raw):
    return {"sha256": digest(raw), "bytes": len(raw),
            "raw_base64": base64.b64encode(raw).decode()}


def decoded(entry):
    raw = base64.b64decode(entry["raw_base64"], validate=True)
    assert digest(raw) == entry["sha256"]
    return raw


def load_archive():
    return json.loads(gzip.decompress(ARCHIVE.read_bytes()))["members"]


def record_requests(members, window="WS128"):
    return [(k, json.loads(decoded(v))) for k, v in sorted(members.items())
            if k.startswith(window + "/run/repeat-1/") and k.endswith("/receipt.json")]


def capture():
    target = HERE / "inputs.json.gz"
    assert not target.exists(), "Refuse to overwrite frozen inputs"
    members = load_archive()
    paths = [METHOD,
        STAGE / "packet108-attribution/BUDGET.md",
        STAGE / "packet108-attribution/budget.json",
        STAGE / "packet110-class-roofline/roofline.json",
        STAGE / "packet122-draft-budget/roofline.json",
        STAGE / "packet128b-attribution/BUDGET.md",
        STAGE / "packet128b-attribution/evidence/budget.json",
        STAGE / "packet134-submission-stalls/evidence/attribution.json",
        STAGE / "packet126-early-draft/simulation.json",
        STAGE / "packet131-snapshot-banks/CENSUS.md",
        STAGE / "packet58t-resident-lookups/ANALYSIS.md",
        STAGE / "packet124c-record-bundle/submission/prepared-a/result.json",
        STAGE.parent / "ops/screen-cleanup/closed.json"]
    for name in ("main.cpp", "rank.hpp", "mtp.hpp", "native_controller.hpp",
                 "p105_runtime.hpp", "strict_snapshot.hpp"):
        paths.append(STAGE / "packet124c-record-bundle" / name)
    for n in (1, 2):
        paths.append(STAGE / f"packet122-draft-budget/evidence/micro-B-{n}/native/iterations.jsonl")
    for key, _ in record_requests(members):
        original = Path(members[key]["source_path"])
        for rank in (0, 1):
            paths.append(original.parent / f"rank{rank}/timings.jsonl")
    prior = subprocess.check_output(["rg", "--files", "-g", "DO-NOT-REPEAT.md"],
                                    cwd=ROOT, stdin=subprocess.DEVNULL, text=True).splitlines()
    paths.extend(ROOT / p for p in prior)
    data = {"schema": "packet135.frozen-inputs.v1",
            "record_archive_sha256": digest(ARCHIVE.read_bytes()),
            "capture_head": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                cwd=ROOT, stdin=subprocess.DEVNULL, text=True).strip(),
            "prior_paths": sorted(prior), "files": {}}
    for path in sorted(set(paths)):
        data["files"][str(path.relative_to(ROOT))] = encoded(path.read_bytes())
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    target.write_bytes(gzip.compress(raw, mtime=0))


def calculate():
    frozen = json.loads(gzip.decompress((HERE / "inputs.json.gz").read_bytes()))
    assert digest(ARCHIVE.read_bytes()) == frozen["record_archive_sha256"]
    files = {p: decoded(v) for p, v in frozen["files"].items()}
    def read(path):
        return files[str(path.relative_to(ROOT))]
    def load(path):
        return json.loads(read(path))
    # Reuse only two pure accounting functions; never execute import-time caps
    # or any old program's main(), and never import runtime/device packages.
    tree = ast.parse(read(METHOD))
    methods = [n for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name in ("duration", "intervals")]
    assert len(methods) == 2
    scope = {}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(METHOD), "exec"), scope)
    members = load_archive()
    result = load(STAGE / "packet124c-record-bundle/submission/prepared-a/result.json")
    rows = []
    requests = []
    timers = defaultdict(list)
    for key, r in record_requests(members):
        assert r["passed"] and r["cached_tokens"] == 0
        assert r["binary_sha256"] == "f77e0e9c50fa9f75d6d0900efa0241911fee34806dc9d118e1d9fab7edb73a01"
        rr = scope["intervals"](r)
        assert len(rr) == 99
        rows.extend(rr)
        requests.append({"prompt_id": r["prompt_id"], "prompt_class": r["prompt_class"],
                         "rows": rr})
        for rank in (0, 1):
            path = Path(members[key]["source_path"]).parent / f"rank{rank}/timings.jsonl"
            for line in read(path).splitlines():
                t = json.loads(line)
                if t["cancelled"] or not (r["prompt_tokens"] <= t["position"] < r["prompt_tokens"] + 99):
                    continue
                label = f"rank{rank}_" + ("speculative" if t["speculative"] else "corrected_or_target")
                timers[label].append(t)
    assert len(requests) == 12 and len(rows) == 1188
    assert sum(x["hit"] for x in rows) == 932
    assert {k: len(v) for k, v in timers.items()} == {
        "rank0_speculative": 1188, "rank0_corrected_or_target": 256,
        "rank1_corrected_or_target": 1188}
    # Each actual interval must reconstruct before making any projection.
    errors = [abs(x["elapsed_ms"] - (max(x["D"], x["R"] + x["C"]) +
              max(x["B"], x["A"] + x["spec_start_offset_ms"]) + x["unresolved_control_gaps_ms"])) for x in rows]
    assert max(errors) < 1e-7
    def rate(vals):
        groups = defaultdict(list)
        for r, durations in zip(requests, vals):
            groups[r["prompt_class"]].append(99000 / sum(durations))
        return st.median(st.median(v) for v in groups.values())
    baseline = rate([[x["elapsed_ms"] for x in r["rows"]] for r in requests])
    assert abs(baseline - result["primary_metric"]["value_tok_s"]) < 1e-8
    def scenario(d=0., a=0., c=0., restore=0., b=0., suffix_exposure=0.):
        # B contains suffix service, so A reductions can move B as well.
        # Exposure is an ASSUMPTION, not inferred from B-A or GPU clocks.
        vals = []
        for r in requests:
            times = []
            for x in r["rows"]:
                ready = max(max(0., x["D"] - d), max(0., x["R"] - restore) + max(0., x["C"] - c))
                race = max(max(0., x["B"] - b - suffix_exposure*a),
                           max(0., x["A"] - a) + x["spec_start_offset_ms"])
                times.append(ready + race + x["unresolved_control_gaps_ms"])
            vals.append(times)
        v = rate(vals)
        return {"assumed_cuts_ms": {"D": d, "A": a, "C": c, "R": restore, "B": b},
                "assumed_suffix_exposure": suffix_exposure, "projected_class_balanced_tok_s": v,
                "projected_gain_percent": 100*(v/baseline-1), "is_measurement": False}
    conditional = {}
    fields = ("elapsed_ms", "A", "B", "C", "D", "R", "spec_start_offset_ms",
              "rank0_slack_ms", "unresolved_control_gaps_ms")
    for hit, label in ((True, "hit"), (False, "miss")):
        rr = [x for x in rows if x["hit"] == hit]
        conditional[label] = {"n": len(rr), "mean_ms": {k: st.mean(x[k] for x in rr) for k in fields}}
    host = {key: {"n": len(ts), "mean": {field: st.mean(t[field] for t in ts)
                    for field in ("prepare_ms", "enqueue_loop_ms", "p76_retirement_ms",
                                  "p76_profiling_ms", "process_major_faults", "launches_issued")}}
            for key, ts in sorted(timers.items())}
    budget = load(STAGE / "packet128b-attribution/evidence/budget.json")
    assert not budget["ranking_usable"] and not budget["summary"]["overhead_bounded"]
    categories = defaultdict(float)
    for row in budget["tables"]:
        if row["kind"] == "gpu" and row["queue"] == "compute":
            categories[f'rank{row["rank"]}/{row["outcome"]}/{row["category"].split("/")[0]}'] += row["mean_ms"]
    draft = []
    for n in (1, 2):
        rows122 = [json.loads(line) for line in read(STAGE / f"packet122-draft-budget/evidence/micro-B-{n}/native/iterations.jsonl").splitlines()]
        for context in (128, 4096):
            z = [r for r in rows122 if r["context"] == context and not r["warmup"]]
            assert len(z) == 40
            draft.append({"process": n, "context": context, "n": len(z),
                          "step_median_ms": st.median(r["gpu_ns"] for r in z)/1e6,
                          "classes_median_ms": {k: st.median(r["classes_ns"][k] for r in z)/1e6
                                                for k in sorted(z[0]["classes_ns"])}})
    embed = st.mean(sum(r["classes_median_ms"][k] for k in
                    ("draft.merge.embedding_norm", "draft.merge.embedding_projected"))
                    for r in draft if r["context"] == 128)
    roof110 = load(STAGE / "packet110-class-roofline/roofline.json")
    target_byte_reference = sum(r["floor_us"]*r["occurrences_per_half"] / 1000
                                for r in roof110["rows"] if r["context"] == 128)
    roof122 = load(STAGE / "packet122-draft-budget/roofline.json")
    draft_byte_reference = {context: sum(r["reference_us"] for r in rr.values()) / 1000
                            for context, rr in roof122["contexts"].items()}
    scenarios = {
        "snapshot_0.20ms_full_exposure": scenario(a=.20, suffix_exposure=1),
        "snapshot_0.30ms_full_exposure": scenario(a=.30, suffix_exposure=1),
        "snapshot_0.20ms_half_exposure": scenario(a=.20, suffix_exposure=.5),
        "snapshot_0.20ms_no_exposure": scenario(a=.20),
        "snapshot_byte_proportional_then_20pct_kernel_transfer": scenario(a=.5223942727272727*(29601792/48627432)*.2, suffix_exposure=1),
        "token_path_central": scenario(d=embed, a=.05, c=.05, suffix_exposure=1),
        "token_path_half_exposure": scenario(d=embed, a=.05, c=.05, suffix_exposure=.5),
        "token_path_no_exposure": scenario(d=embed, a=.05, c=.05),
        "draft_embedding_precompute_only": scenario(d=embed),
        "target_prepare_half_only": scenario(a=.05, c=.05, suffix_exposure=1),
        "target_prepare_zero_optimistic": scenario(a=host["rank0_speculative"]["mean"]["prepare_ms"],
                               c=host["rank0_corrected_or_target"]["mean"]["prepare_ms"], suffix_exposure=1),
        "event_query_0.10ms_exposed": scenario(b=.10),
        "snapshot_plus_token_path_central": scenario(d=embed, a=.25, c=.05, suffix_exposure=1),
        "local_practical_optimistic_envelope": scenario(d=.10, a=.40, c=.10, suffix_exposure=1),
        "zero_draft_fixed_target_optimistic": scenario(d=max(x["D"] for x in rows)),
    }
    # Quantify the coupled-head dependence needed for each brief's +0.5% gate.
    thresholds = {}
    for name, cuts in (("snapshot_0.20ms", {"a": .20}),
                       ("token_path", {"d": embed, "a": .05, "c": .05})):
        lo, hi = 0., 1.
        for _ in range(50):
            mid = (lo+hi)/2
            if scenario(**cuts, suffix_exposure=mid)["projected_gain_percent"] >= .5:
                hi = mid
            else:
                lo = mid
        thresholds[name] = hi
    pattern = re.compile(r"lookup|embedding|token.*prepar|profil|retir|snapshot|bank|draft|copy|replay", re.I)
    audit = []
    for path in frozen["prior_paths"]:
        lines = files[path].decode().splitlines()
        audit.append({"path": path, "sha256": digest(files[path]),
                      "matches": [{"line": i+1, "text": line} for i, line in enumerate(lines) if pattern.search(line)]})
    return {"schema": "packet135.critical-path.v1", "device_executed": False,
        "submission_eligible": False, "measured_candidate_gain": None,
        "record_archive_sha256": frozen["record_archive_sha256"],
        "inputs_sha256": digest((HERE/"inputs.json.gz").read_bytes()),
        "selection": result["bundle_selection"], "baseline_class_balanced_tok_s": baseline,
        "pooled_interval_mean_ms": st.mean(x["elapsed_ms"] for x in rows),
        "pooled_interval_rate_tok_s": 1000/st.mean(x["elapsed_ms"] for x in rows),
        "max_accounting_error_ms": max(errors), "conditional": conditional,
        "record_host_timers": host, "diagnostic128b_grouped_compute_ms": dict(sorted(categories.items())),
        "byte_references_not_hardware_floors": {
            "packet110_representative_half_ctx128_ms_at537GBs": target_byte_reference,
            "packet122_draft_ms_at555GBs": draft_byte_reference,
            "snapshot_full_read_write_ms_at537GBs": 2*48627432/537e6,
            "snapshot_remaining_read_write_ms_at537GBs": 2*19025640/537e6,
            "draft_embedding_projection_table_bytes": 248320*2560*2},
        "draft122": draft, "draft_static_embedding_kernel_budget_ms": embed,
        "scenarios": scenarios, "required_suffix_exposure_fraction": thresholds,
        "closed": load(STAGE.parent/"ops/screen-cleanup/closed.json"),
        "prior_audit": audit,
        "input_files": {p: {k:v[k] for k in ("sha256", "bytes")} for p,v in frozen["files"].items()},
        "limits": ["128b is diagnostic; no division by its overhead ratio.",
                   "Scenarios assume achievable cuts and suffix exposure; neither is measured.",
                   "Control remainder is retained; accounting is not predictive validation.",
                   "Host timers overlap device work; draft events are inside D.",
                   "No exact numeric floor exists for untimed subsegments."]}


def main():
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    assert not (args.capture and args.check)
    if args.capture:
        capture()
    report = calculate()
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+"\n"
    target = HERE/"model.json"
    if args.check:
        assert target.read_text() == text, "Saved report differs from recomputation"
    else:
        target.write_text(text)
    print(json.dumps({"passed": True, "baseline": report["baseline_class_balanced_tok_s"],
        "hit_miss": report["conditional"], "prior_files": len(report["prior_audit"]),
        "scenarios": report["scenarios"], "thresholds": report["required_suffix_exposure_fraction"],
        "peak_rss_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}, indent=2))


if __name__ == "__main__":
    main()
