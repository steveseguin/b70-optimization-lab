#!/usr/bin/env python3
"""CPU-only packet140 evidence capture and projection; never imports a runtime.

Run with nice19, taskset 8-15,24-31, python3 -B, stdin /dev/null.
--capture freezes originals once. --check verifies reproducibility without writes.
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
import shutil
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = HERE.parent
PREFIX = str(STAGE.relative_to(ROOT)) + "/"
PATTERN = r"(?i)expert|gate|norm|route|recurr|fusion|fused|gemv|reduct|split32|tile|lookup|prefetch|SLM|GRF|QSA|GDN|combine|conv|packed|scale|nonfinite|NaN"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(raw):
    return {"sha256": sha(raw), "bytes": len(raw),
            "base64": base64.b64encode(raw).decode()}


def decoded(item):
    raw = base64.b64decode(item["base64"], validate=True)
    assert len(raw) == item["bytes"] and sha(raw) == item["sha256"]
    return raw


def capture():
    assert not (HERE / "inputs.json.gz").exists()
    assert shutil.disk_usage(ROOT).free >= 25_000_000_000
    prior = subprocess.check_output(
        ["rg", "--files", "--hidden", "-g", "*DO-NOT-REPEAT*", "-g", "!.git"],
        cwd=ROOT, stdin=subprocess.DEVNULL, text=True).splitlines()
    prior = sorted(p for p in prior if not p.startswith(str(HERE.relative_to(ROOT))))
    # Search every discovered negative index, not only files whose names mention
    # the requested packet numbers. Retain the complete originals as well.
    result = subprocess.run(["rg", "-n", "-e", PATTERN, "--", *prior],
        cwd=ROOT, stdin=subprocess.DEVNULL, text=True, capture_output=True)
    assert result.returncode in (0, 1), result.stderr
    names = [
        "packet128b-attribution/evidence/budget.json",
        "packet128b-attribution/BUDGET.md",
        "packet134-submission-stalls/evidence/attribution.json",
        "packet110-class-roofline/roofline.json",
        "packet110-class-roofline/ROOFLINE.md",
        "packet135-critical-path/ANALYSIS.md",
        "packet126-early-draft/method/p85_model.py",
        "packet136-record-bundle/selection.json",
        "packet136-record-bundle/memory-plan.json",
        "packet136-record-bundle/p90_expert.hpp",
        "packet136-record-bundle/p90_layout.hpp",
        "packet136-record-bundle/p33_candidates.hpp",
        "packet136-record-bundle/p60_kernels.hpp",
        "packet109-other-fusion/CENSUS.md",
        "packet104-tile-transpose/micro-closeout.md",
    ]
    paths = prior + [PREFIX + n for n in names] + [
        "experiments/own-xpu-runtime/ops/screen-cleanup/closed.json",
        "notes/2026-10-18-own-runtime-packet104-micro-result.md",
    ]
    archive_path = STAGE / "packet124c-record-bundle/submission/prepared-a/evidence.json.gz"
    archive = json.loads(gzip.decompress(archive_path.read_bytes()))["members"]
    receipts = {}
    for key, value in archive.items():
        if key.startswith("WS128/run/repeat-1/") and key.endswith("/receipt.json"):
            raw = base64.b64decode(value["raw_base64"], validate=True)
            assert sha(raw) == value["sha256"]
            receipts[key] = encoded(raw)
    assert len(receipts) == 12
    inputs = {"schema": "packet140.frozen-inputs.v1", "prior_paths": prior,
        "search_pattern": PATTERN, "search_output": result.stdout,
        "capture_head": subprocess.check_output(["git", "rev-parse", "HEAD"],
            cwd=ROOT, stdin=subprocess.DEVNULL, text=True).strip(),
        "archive_sha256": sha(archive_path.read_bytes()),
        "receipts": receipts,
        "files": {p: encoded((ROOT / p).read_bytes()) for p in sorted(set(paths))}}
    (HERE / "inputs.json.gz").write_bytes(gzip.compress(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode(), mtime=0))


def calculate():
    frozen = json.loads(gzip.decompress((HERE / "inputs.json.gz").read_bytes()))
    files = {p: decoded(v) for p, v in frozen["files"].items()}
    def load(name):
        return json.loads(files[PREFIX + name])
    tree = ast.parse(files[PREFIX + "packet126-early-draft/method/p85_model.py"])
    methods = [n for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name in ("duration", "intervals")]
    assert len(methods) == 2
    scope = {}
    exec(compile(ast.Module(body=methods, type_ignores=[]), "frozen-accounting", "exec"), scope)
    requests = []
    for key, item in sorted(frozen["receipts"].items()):
        receipt = json.loads(decoded(item))
        assert receipt["passed"] and receipt["cached_tokens"] == 0
        rows = scope["intervals"](receipt)
        assert len(rows) == 99
        for x in rows:
            reconstructed = max(x["D"], x["R"] + x["C"]) + max(
                x["B"], x["A"] + x["spec_start_offset_ms"]) + x["unresolved_control_gaps_ms"]
            assert abs(reconstructed - x["elapsed_ms"]) < 1e-7
        requests.append((receipt["prompt_class"], rows))
    def rate(cut=0.):
        classes = defaultdict(list)
        # Same net cut on both overlapped target halves; one additional cut on
        # the serial correction half on misses. No double count of two ranks.
        # B follows its own body OR the equally accelerated suffix dependency,
        # never the sum of those two effects. Full exposure is optimistic.
        for kind, rows in requests:
            times = []
            for x in rows:
                ready = max(x["D"], x["R"] + max(0., x["C"] - cut))
                race = max(max(0., x["B"] - cut),
                           max(0., x["A"] - cut) + x["spec_start_offset_ms"])
                times.append(ready + race + x["unresolved_control_gaps_ms"])
            classes[kind].append(99000 / sum(times))
        return statistics.median(statistics.median(v) for v in classes.values())
    baseline = rate()
    assert abs(baseline - 58.2238342935355) < 1e-8
    rows = [x for _, rr in requests for x in rr]
    assert len(rows) == 1188 and sum(x["hit"] for x in rows) == 932
    def project(raw_ms, transfer):
        value = rate(raw_ms * transfer)
        return {"raw_half_saving_ms": raw_ms, "transfer": transfer,
            "net_half_saving_ms": raw_ms * transfer,
            "projected_class_balanced_tok_s": value,
            "projected_gain_percent": 100 * (value / baseline - 1),
            "measured": False}
    lo, hi = 0., 2.
    for _ in range(60):
        mid = (lo + hi) / 2
        if rate(mid) >= 1.03 * baseline:
            hi = mid
        else:
            lo = mid
    budget = load("packet128b-attribution/evidence/budget.json")
    assert not budget["ranking_usable"] and not budget["summary"]["overhead_bounded"]
    categories = {r["category"]: r["mean_ms"] for r in budget["tables"]
        if r["rank"] == 1 and r["outcome"] == "hit" and r["queue"] == "compute"
        and r["kind"] == "gpu" and r["category"].startswith(
            ("attention/", "hc_norm_merge/", "moe_experts/", "shared_expert/"))}
    categories["other"] = next(r["mean_ms"] for r in budget["tables"]
        if r["rank"] == 1 and r["outcome"] == "hit" and r["kind"] == "gpu"
        and r["queue"] == "compute" and r["category"] == "other")
    groups = {
        "dense_attention": ["attention/" + k for k in ("attention", "gdn.qkv", "gdn.z", "qsa.qgate")],
        "gate_up": ["moe_experts/expsgate"],
        "down": ["moe_experts/expsdown"],
        "hc_gate": ["hc_norm_merge/hc." + k + ".gate" for k in ("a", "f")],
        "hc_low": ["hc_norm_merge/hc." + k + ".low" for k in ("a", "f")],
        "hc_norm": ["hc_norm_merge/hc." + k + ".norm" for k in ("a", "f")],
        "route": ["moe_experts/route"],
        "router_tuple": ["moe_experts/router"],
        "recurrence": ["attention/gdn.recurrence"],
        "qsa_attention_select": ["attention/qsa.attention", "attention/qsa.select"],
        "shared_fused": ["shared_expert/shexpdown"],
        "small_dense": ["attention/" + k for k in ("gdn.a", "qsa.ik", "qsa.iq", "qsa.k", "qsa.v")],
        "small_remaining": ["moe_experts/expsact", "moe_experts/ffn.combine",
            "attention/gdn.conv", "attention/gdn.gated", "attention/qsa.prepare", "attention/qsa.pool", "other"],
    }
    assigned = [k for values in groups.values() for k in values]
    assert len(assigned) == len(set(assigned)) and set(assigned) == set(categories)
    totals = {g: sum(categories[k] for k in keys) for g, keys in groups.items()}
    # Explicit engineering WHAT-IF assumptions, not fitted measurements. They
    # cannot alone admit work: the distinct mechanism must also justify them.
    fractions = {g: .20 for g in groups}
    fractions["dense_attention"] = .10
    fractions["hc_norm"] = .50
    scenarios = {g: {"diagnostic_half_ms": value,
        "hypothetical_operator_reduction": fractions[g],
        "central_20pct_transfer": project(value * fractions[g], .2),
        "sensitivity_80pct_transfer": project(value * fractions[g], .8),
        "impossible_delete_whole_class_20pct_transfer": project(value, .2),
        "required_raw_reduction_fraction_20pct_transfer": hi / (.2 * value),
        "required_raw_reduction_fraction_80pct_transfer": hi / (.8 * value)}
        for g, value in totals.items()}
    ranked = sorted(scenarios, key=lambda k: scenarios[k]["central_20pct_transfer"]["projected_gain_percent"], reverse=True)
    assert all(s["central_20pct_transfer"]["projected_gain_percent"] < 3 for s in scenarios.values())
    n1_groups = ("dense_attention", "hc_gate", "hc_low", "router_tuple", "shared_fused", "small_dense")
    n1_raw = sum(totals[g] * fractions[g] for g in n1_groups)
    n1 = {"groups": list(n1_groups), "optimistically_all_sites_eligible": True,
        "central_20pct_transfer": project(n1_raw, .2),
        "sensitivity_80pct_transfer": project(n1_raw, .8),
        "required_transfer_for_3pct": hi / n1_raw}
    assert n1["central_20pct_transfer"]["projected_gain_percent"] < 3
    report = {"schema": "packet140.analysis.v1", "baseline_tok_s": baseline,
        "baseline_identity": "packet124c WS128; iq3-p49-split32-v1; bundle7",
        "bundle8_class_times_measured": False, "packet128b_overhead_passed": False,
        "inputs_sha256": sha((HERE / "inputs.json.gz").read_bytes()),
        "capture_head": frozen["capture_head"], "prior_file_count": len(frozen["prior_paths"]),
        "prior_audit": [{"path": p, "sha256": sha(files[p]), "matching_lines": [
            {"line": n, "text": line} for n, line in enumerate(files[p].decode().splitlines(), 1)
            if re.search(PATTERN, line)]} for p in frozen["prior_paths"]],
        "closed": json.loads(files["experiments/own-xpu-runtime/ops/screen-cleanup/closed.json"]),
        "record_intervals": len(rows), "record_misses": sum(not x["hit"] for x in rows),
        "required_net_half_saving_ms_for_3pct": hi,
        "required_raw_half_saving_ms_at20pct": hi / .2,
        "required_raw_half_saving_ms_at80pct": hi / .8,
        "current_body_proxy_ms": sum(categories.values()),
        "categories": categories, "ranked_groups": ranked, "scenarios": scenarios,
        "n1_whole_eligible_path": n1,
        "selected_lever": None, "decision": "CLOSED_NO_SUPPORTED_3_PERCENT_LEVER",
        "device_executed": False, "submission_eligible": False}
    return report, frozen["search_output"]


def main():
    # Caps belong only in this CPU-only entry; never inherited by device work.
    resource.setrlimit(resource.RLIMIT_AS, (4_000_000_000, 4_000_000_000))
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    assert not (args.capture and args.check)
    if args.capture:
        capture()
    report, history = calculate()
    output = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.check:
        assert (HERE / "analysis.json").read_text() == output
        assert (HERE / "prior-search.txt").read_text() == history
    else:
        assert shutil.disk_usage(ROOT).free >= 25_000_000_000
        (HERE / "analysis.json").write_text(output)
        (HERE / "prior-search.txt").write_text(history)
    print(json.dumps({"checked": args.check, "prior_files": report["prior_file_count"],
        "baseline": report["baseline_tok_s"],
        "required_net_half_ms": report["required_net_half_saving_ms_for_3pct"],
        "n1_whole_path": report["n1_whole_eligible_path"],
        "ranked": [(k, report["scenarios"][k]["diagnostic_half_ms"],
            report["scenarios"][k]["central_20pct_transfer"]["projected_gain_percent"],
            report["scenarios"][k]["sensitivity_80pct_transfer"]["projected_gain_percent"])
            for k in report["ranked_groups"]],
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))


if __name__ == "__main__":
    main()
