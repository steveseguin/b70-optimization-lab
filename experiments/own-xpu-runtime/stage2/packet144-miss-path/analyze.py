#!/usr/bin/env python3
"""Small saved-receipt analysis only; no model/runtime imports or device work."""
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
METHOD = STAGE / "packet126-early-draft/method/p85_model.py"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def relative(path):
    return str(path.relative_to(ROOT))


def capture():
    assert not (HERE / "inputs.json.gz").exists()
    paths = subprocess.check_output(
        ["rg", "--files", "-g", "*DO-NOT-REPEAT*"], cwd=ROOT,
        stdin=subprocess.DEVNULL, text=True).splitlines()
    paths = sorted(p for p in paths if "packet144-miss-path/" not in p)
    files = {}
    def keep(path):
        raw = path.read_bytes()
        files[relative(path)] = {"sha256": sha(raw), "text": raw.decode()}
    for p in paths:
        keep(ROOT / p)
    for name in ("native_controller.hpp", "rank.hpp", "mtp.hpp",
                 "strict_snapshot.hpp", "p105_runtime.hpp", "selection.json"):
        keep(STAGE / "packet136-record-bundle" / name)
    for name in ("packet135-critical-path/ANALYSIS.md",
                 "packet135-critical-path/model.json",
                 "packet128b-attribution/BUDGET.md",
                 "packet134-submission-stalls/ATTRIBUTION.md"):
        keep(STAGE / name)
    keep(METHOD)
    pins = {}
    for packet in ("packet124c-record-bundle", "packet136-record-bundle"):
        for name in ("result.json", "evidence.json.gz"):
            path = STAGE / packet / "submission/prepared-a" / name
            pins[relative(path)] = sha(path.read_bytes())
    data = {"schema": "packet144.inputs.v1", "head": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, stdin=subprocess.DEVNULL,
        text=True).strip(), "negative_indexes": paths, "files": files,
        "tracked_input_sha256": pins,
        "scope": "Saved small receipts/source only; no model or full-shape reads"}
    (HERE / "inputs.json.gz").write_bytes(gzip.compress(
        json.dumps(data, sort_keys=True).encode(), mtime=0))


def calculate():
    frozen = json.loads(gzip.decompress((HERE / "inputs.json.gz").read_bytes()))
    for item in frozen["files"].values():
        assert sha(item["text"].encode()) == item["sha256"]
    for path, digest in frozen["tracked_input_sha256"].items():
        assert sha((ROOT / path).read_bytes()) == digest, path
    tree = ast.parse(frozen["files"][relative(METHOD)]["text"])
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in ("duration", "intervals")]
    assert len(funcs) == 2
    scope = {}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(METHOD), "exec"), scope)
    output = {"schema": "packet144.analysis.v1", "is_device_measurement": False,
              "input_sha256": sha((HERE / "inputs.json.gz").read_bytes()),
              "negative_index_count": len(frozen["negative_indexes"]),
              "gate_percent": 3, "gate_passed": False, "records": {}}
    for packet in ("packet124c-record-bundle", "packet136-record-bundle"):
        directory = STAGE / packet / "submission/prepared-a"
        result = json.loads((directory / "result.json").read_bytes())
        members = json.loads(gzip.decompress((directory / "evidence.json.gz").read_bytes()))["members"]
        requests = []
        for key, member in sorted(members.items()):
            if not (key.startswith("WS128/run/repeat-1/") and key.endswith("/receipt.json")):
                continue
            raw = base64.b64decode(member["raw_base64"], validate=True)
            assert sha(raw) == member["sha256"]
            receipt = json.loads(raw)
            assert receipt["passed"] and receipt["cached_tokens"] == 0
            assert receipt["arithmetic"] == "iq3-p49-split32-v1"
            assert receipt["binary_sha256"] == result["artifacts_sha256"]["device/own-rt-iq3"]
            rows = scope["intervals"](receipt)
            assert len(rows) == 99
            guesses = {g["position"]: g for g in receipt["guess_rows"]}
            for row in rows:
                row["actual_token"] = guesses[row["position"]]["actual"]
            requests.append((receipt["prompt_id"], receipt["prompt_class"], rows))
        assert len(requests) == 12
        rows = [r for _, _, rr in requests for r in rr]
        assert len(rows) == 1188
        def model(r, c=0, restore=0, b=0):
            return (max(r["D"], max(0, r["R"]-restore) + max(0, r["C"]-c))
                    + max(max(0, r["B"]-(b if not r["hit"] else 0)),
                          r["A"]+r["spec_start_offset_ms"])
                    + r["unresolved_control_gaps_ms"])
        error = max(abs(model(r)-r["elapsed_ms"]) for r in rows)
        assert error < 1e-7
        def rate(transform):
            classes = defaultdict(list)
            for _, cls, rr in requests:
                classes[cls].append(99000 / sum(transform(r) for r in rr))
            return st.median(st.median(v) for v in classes.values())
        baseline = rate(lambda r: r["elapsed_ms"])
        assert abs(baseline-result["primary_metric"]["value_tok_s"]) < 1e-8
        def gain(transform):
            return 100*(rate(transform)/baseline-1)
        def threshold(transform, hi=11.):
            lo = 0.
            assert gain(lambda r: transform(r, hi)) > 3
            for _ in range(70):
                mid = (lo+hi)/2
                if gain(lambda r: transform(r, mid)) < 3:
                    lo = mid
                else:
                    hi = mid
            return hi
        conditional = {}
        for hit in (True, False):
            rr = [r for r in rows if r["hit"] == hit]
            conditional["hit" if hit else "miss"] = {"n": len(rr), "mean_ms": {
                k: st.mean(r[k] for r in rr) for k in ("D", "R", "C", "A", "B", "elapsed_ms")}}
        scenarios = {}
        for c in (0.05, 0.102197, 0.5, 0.6, 1., 2., 2.3, 3.):
            scenarios[f"correction_cut_{c:g}_ms"] = gain(lambda r: model(r, c=c))
        scenarios["hide_entire_restore_upper_bound"] = gain(lambda r: model(r, restore=100))
        scenarios["hide_restore_and_0.102197ms_preparation_upper_bound"] = gain(
            lambda r: model(r, restore=100, c=0.102197))
        scenarios["remove_entire_rank1_B_on_misses_upper_bound"] = gain(lambda r: model(r, b=100))
        # Ideal miss rescue: turn a fraction of every miss into a hit, at no
        # cost. This is a sensitivity, not observed draft acceptance or tokens.
        def rescue(r, fraction):
            return r["elapsed_ms"] - fraction*(max(r["D"], r["R"]+r["C"])-r["D"])
        rescue_fraction = threshold(rescue, hi=1.)
        misses = sum(not r["hit"] for r in rows)
        output["records"][packet] = {
            "baseline_tok_s": baseline, "pooled_mean_ms": st.mean(r["elapsed_ms"] for r in rows),
            "max_reconstruction_error_ms": error, "conditional": conditional,
            "miss_fraction": misses/len(rows),
            "correction_cut_ms_for_3percent": threshold(lambda r, s: model(r, c=s)),
            "free_miss_rescue_fraction_for_3percent": rescue_fraction,
            "acceptance_percentage_point_increase_for_3percent": 100*rescue_fraction*misses/len(rows),
            "draft_head_extension_retrospective_ceiling": {
                "unchanged_prefix_rows": 80128,
                "miss_labels_outside_prefix": sum(not r["hit"] and r["actual_token"] >= 80128 for r in rows),
                "ideal_gain_if_all_outside_prefix_misses_rescued_percent": gain(
                    lambda r: rescue(r, float(not r["hit"] and r["actual_token"] >= 80128))),
                "assumptions": "Free full-head extension on every interval, not just after misses; unchanged prefix logits; all eligible misses rescued; no new misses. Retrospective upper sensitivity only, not independent acceptance evidence or prefix selection."},
            "scenarios_gain_percent_not_measurements": scenarios}
    regex = re.compile(r"miss|restore|prefetch|early|draft|handoff|hand.off|packet12[01879]|packet13[0245]|depth|split", re.I)
    output["negative_index_matches"] = {p: [{"line": i, "text": line}
        for i, line in enumerate(frozen["files"][p]["text"].splitlines(), 1) if regex.search(line)]
        for p in frozen["negative_indexes"]}
    return output


def main():
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.capture:
        capture()
    result = calculate()
    encoded = json.dumps(result, indent=2, sort_keys=True)+"\n"
    if args.check:
        assert (HERE / "model.json").read_text() == encoded
    else:
        (HERE / "model.json").write_text(encoded)
    print(json.dumps({"checked": args.check, "negative_indexes": result["negative_index_count"],
                      "records": result["records"]}, indent=2))


if __name__ == "__main__":
    main()
