#!/usr/bin/env python3
"""CPU receipt/metadata analysis only; no runtime imports or model payloads.

--capture freezes small source/receipt inputs once. Default writes analysis.json
inside this new packet; --check reproduces it without writing. External record
archive is already tracked and is hash-bound rather than duplicated.
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
S = ROOT / "experiments/own-xpu-runtime/stage2"
RECORD = S / "packet136-record-bundle/submission/prepared-a"
CENSUS = "packet136-record-bundle/evidence/shape-ab825c135700b7e9abf2ac9ba3bc8865e0d280ccc7191bd1b5a711c26fa77b9b-census.json.gz"
TAGS = ["p105b-eeccee46f0f1-B-smoke12",
        "p106b-13e3630d590c-B-grid-1-head-split"]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def capture():
    paths = [S / p for p in [
        CENSUS, "packet136-record-bundle/parent-snapshot/memory-plan.json",
        "packet136-record-bundle/native_controller.hpp",
        "packet136-record-bundle/rank.hpp", "packet136-record-bundle/p60_math.hpp",
        "packet136-record-bundle/p105_runtime.hpp",
        "packet105b-head-split/p105_runtime.hpp",
        "packet106b-draft-split/p105_runtime.hpp",
        "packet126-early-draft/method/p85_model.py",
        "packet128b-attribution/BUDGET.md",
        "packet134-submission-stalls/ATTRIBUTION.md",
        "packet135-critical-path/ANALYSIS.md",
        "packet144-miss-path/ANALYSIS.md",
        "packet147-lever-synthesis/PLAN.md",
        "packet110-class-roofline/BYTE-MODEL.md",
        "packet34-replay-bench/directory.tsv",
        "packet87t-transfer-micro/RESULT.json",
        "packet87t-transfer-micro/microbench.cpp",
        "packet136-record-bundle/submission/prepared-a/result.json",
    ]]
    paths += list((S / "packet136-record-bundle/selections").glob("*banks*/memory-plan.json"))
    negatives = ["packet12-peer", "packet68b-batched-rows", "packet68c-m2-from-production",
                 "packet71c-depth2-engine", "packet79-draft-rank0", "packet105b-head-split",
                 "packet106b-draft-split", "packet119-down-warm", "packet120-placement",
                 "packet121-miss-table", "packet123-partial-placement",
                 "packet125-miss-transfer", "packet127-head-retune",
                 "packet128b-attribution", "packet130-suffix-interleave",
                 "packet136-record-bundle", "packet138-xlayer-prefetch",
                 "packet140-body-lever", "packet144-miss-path"]
    paths += [S / n / "DO-NOT-REPEAT.md" for n in negatives]
    for tag in TAGS:
        root = S / "screen/v4-lanes/evidence" / tag
        paths += [root / "summary.json", root / "identity.json"]
        logs = sorted(root.glob("run/*/rank*/p105-transfers.jsonl"))
        assert len(logs) == (2 if tag == TAGS[0] else 30)
        paths += logs
    files = {}
    for p in sorted(set(paths)):
        raw = p.read_bytes()
        files[str(p.relative_to(ROOT))] = {"sha256": digest(raw),
                                          "raw_base64": base64.b64encode(raw).decode()}
    archive = RECORD / "evidence.json.gz"
    data = {"schema": "packet148.inputs.v1", "files": files,
            "external": {str(archive.relative_to(ROOT)): digest(archive.read_bytes())}}
    dest = HERE / "inputs.json.gz"
    assert not dest.exists(), "never replace a frozen capture"
    dest.write_bytes(gzip.compress(json.dumps(data, sort_keys=True).encode(), mtime=0))


def balanced(pairs):
    groups = defaultdict(list)
    for key, value in pairs:
        groups[key].append(value)
    return st.median(st.median(v) for v in groups.values())


def calculate():
    capture_raw = (HERE / "inputs.json.gz").read_bytes()
    inputs = json.loads(gzip.decompress(capture_raw))
    files = {}
    for name, entry in inputs["files"].items():
        raw = base64.b64decode(entry["raw_base64"])
        assert digest(raw) == entry["sha256"], name
        files[name] = raw
    def raw(rel):
        return files[str((S / rel).relative_to(ROOT))]
    def load(rel):
        return json.loads(raw(rel))
    method = raw("packet126-early-draft/method/p85_model.py")
    assert digest(method) == "6627ffa350361a85aed5160f1f5738409cb23bab4f9ca1f34fea7317a0b63ad4"
    nodes = [n for n in ast.parse(method).body
             if isinstance(n, ast.FunctionDef) and n.name in ("duration", "intervals")]
    scope = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "pinned-p85-functions", "exec"), scope)
    archive_name, archive_hash = next(iter(inputs["external"].items()))
    archive = (ROOT / archive_name).read_bytes()
    assert digest(archive) == archive_hash
    members = json.loads(gzip.decompress(archive))["members"]
    requests = []
    for name, entry in sorted(members.items()):
        if not (name.startswith("WS128/run/repeat-1/") and name.endswith("/receipt.json")):
            continue
        data = base64.b64decode(entry["raw_base64"])
        assert digest(data) == entry["sha256"]
        receipt = json.loads(data)
        assert receipt["passed"] and receipt["cached_tokens"] == 0
        requests.append((receipt["prompt_class"], scope["intervals"](receipt)))
    rows = [r for _, rr in requests for r in rr]
    assert len(requests) == 12 and len(rows) == 1188
    def interval(r, cut=0):
        return (max(r["D"], r["R"] + max(0, r["C"] - cut))
                + max(r["B"], r["A"] + r["spec_start_offset_ms"])
                + r["unresolved_control_gaps_ms"])
    assert max(abs(interval(r) - r["elapsed_ms"]) for r in rows) < 1e-7
    def rate(cut=0):
        return balanced((cls, 99000 / sum(interval(r, cut) for r in rr)) for cls, rr in requests)
    base = rate()
    declared = load("packet136-record-bundle/submission/prepared-a/result.json")
    assert declared["promotionIdentity"]["arithmetic"] == "iq3-p49-split32-v1"
    assert declared["artifacts_sha256"]["device/own-rt-iq3"] == "fd7e8b6f5fb24c5042d051f59026091a9184c0f15149d7de110528b7d3ac5451"
    assert declared["bundle_selection"]["layer_boundary"] == 24
    assert declared["bundle_selection"]["draft_rank"] == 1
    assert declared["bundle_selection"]["rollback_state"] == "banks"
    assert not declared["realistic_final_gate"]["passed"]
    assert abs(base - declared["primary_metric"]["value_tok_s"]) < 1e-8
    def gain(cut):
        return 100 * (rate(cut) / base - 1)
    lo, hi = 0., 10.
    for _ in range(70):
        mid = (lo + hi) / 2
        if gain(mid) < 2:
            lo = mid
        else:
            hi = mid
    result = {"schema": "packet148.correction-graph-analysis.v1",
              "scope": "CPU projections; no candidate speed or quality measurement",
              "inputs_sha256": digest(capture_raw),
              "external_inputs": inputs["external"],
              "source_sha256": {k: v["sha256"] for k, v in inputs["files"].items()},
              "record": {"rate_tok_s": base, "intervals": len(rows),
                         "hits": sum(r["hit"] for r in rows),
                         "misses": sum(not r["hit"] for r in rows),
                         "cut_ms_for_2percent": hi,
                         "miss_means_ms": {k: st.mean(r[k] for r in rows if not r["hit"])
                                           for k in ["C", "D", "R", "A", "B"]},
                         "minimum_miss_B_minus_A_offset_ms": min(r["B"]-r["A"]-r["spec_start_offset_ms"] for r in rows if not r["hit"]),
                         "sensitivities_percent": {str(c): gain(c) for c in [.5, 1, 1.5, 2, 3]}}}
    transfers = {}
    for tag in TAGS:
        root = str((S / "screen/v4-lanes/evidence" / tag).relative_to(ROOT))
        assert json.loads(files[root + "/summary.json"])["passed"]
        groups = defaultdict(list)
        for name, data in files.items():
            if name.startswith(root + "/run/") and name.endswith("/p105-transfers.jsonl"):
                for line in data.splitlines():
                    r = json.loads(line)
                    field = "host_us" if "host_us" in r else "host_dependency_wait_us"
                    groups[(r["leg"], field, r["bytes"])].append(r[field])
        transfers[tag] = {"/".join(map(str, k)): {"n": len(v), "median_us": st.median(v),
                         "mean_us": st.mean(v), "p90_nearest_lower_us": sorted(v)[int(.9*(len(v)-1))]}
                          for k, v in sorted(groups.items())}
    result["production_transfers"] = transfers
    p87 = load("packet87t-transfer-micro/RESULT.json")["summary_us"]
    result["micro_transfers"] = {k: v["total_us"] for k, v in p87.items()}
    census = json.loads(gzip.decompress(raw(CENSUS)))
    weights = defaultdict(int)
    layers = defaultdict(lambda: defaultdict(int))
    for a in census["allocations"]:
        if a["memory"] != "device":
            continue
        m = re.search(r"blk\.(\d+)\.(.*)", a["label"])
        if m:
            layers[int(m[1])][a["category"]] += a["bytes"]
            if a["category"] == "weights":
                weights[m[2]] += a["bytes"]
    plan_name = next(k for k in files if "/selections/" in k and k.endswith("/memory-plan.json"))
    plan = json.loads(files[plan_name])
    ranks = plan["placements"]["1"]["capacities"]["4096"]["ranks"]
    margin = ranks[1]["arena_headroom_bytes"]
    assert margin == 786269478 and census["totals"]["device"] == ranks[0]["arena_device_bytes"]
    expert_bytes = sum(weights[k] for k in ["ffn_gate_exps.weight", "ffn_up_exps.weight", "ffn_down_exps.weight"])
    result["memory"] = {"scope": plan["scope"], "ranks": ranks,
                        "weights_by_tensor_suffix": dict(weights),
                        "layer_categories": dict(layers),
                        "all_first_half_weights": sum(weights.values()),
                        "expert_bank_bytes": expert_bytes,
                        "expert_half_rows_bytes": expert_bytes / 2,
                        "expert_equal_fraction_max_before_scratch": margin / expert_bytes,
                        "selected10_half_rows_bytes_all_layers": expert_bytes / 512 * 10 / 2,
                        "layer23_packed_expert_bytes": 2*268697600 + 471859200}
    # Hit class times contain one half. Miss class times contain C plus A.
    # Do NOT halve a failed-overhead miss aggregate and call it measured C.
    times = {}
    for line in raw("packet128b-attribution/BUDGET.md").decode().splitlines():
        cols = [c.strip() for c in line.split("|")]
        if len(cols) > 7 and cols[1:4] == ["0", "hit", "compute"]:
            times[cols[4]] = float(cols[5])
    def t(*names):
        return sum(times[n] for n in names)
    def w(*names):
        return sum(weights[n] for n in names)
    # Optimistic independent islands. Only the named qkv/z pair shares an
    # input. HC low->gate and expert gate->act->down remain separate islands.
    islands = [
        ("GDN qkv+z", 18, t("attention/gdn.qkv", "attention/gdn.z"), w("attn_qkv.weight", "attn_gate.weight"), 5120, 16384),
        ("attention output", 24, t("attention/attention"), w("ssm_out.weight", "attn_output.weight"), 12288, 2560),
        ("QSA qgate", 6, t("attention/qsa.qgate"), w("attn_q.weight"), 5120, 12288),
        ("HC low A", 24, t("hc_norm_merge/hc.a.low"), w("hc_attn_down.weight", "hc_attn_inject.weight"), 20480, 648),
        ("HC low F", 24, t("hc_norm_merge/hc.f.low"), w("hc_ffn_down.weight", "hc_ffn_inject.weight"), 20480, 648),
        ("HC gate A", 24, t("hc_norm_merge/hc.a.gate"), w("hc_attn_up.weight"), 10880, 12800),
        ("HC gate F", 24, t("hc_norm_merge/hc.f.gate"), w("hc_ffn_up.weight"), 10880, 12800),
        ("router tuple", 24, t("moe_experts/router"), w("ffn_gate_inp.weight", "ffn_gate_shexp.weight", "ffn_up_shexp.weight", "ffn_gate_inp_shexp.weight"), 5120, 1794),
        ("expert gate+up", 24, t("moe_experts/expsgate"), w("ffn_gate_exps.weight", "ffn_up_exps.weight"), 5240, 12840),
        ("expert down", 24, t("moe_experts/expsdown"), w("ffn_down_exps.weight"), 12920, 25620),
        ("shared down", 24, t("shared_expert/shexpdown"), w("ffn_down_shexp.weight"), 1280, 2560),
    ]
    # Round up payload to a measured 5 KiB/20 KiB transaction, split larger
    # payloads. This is a scheduling assumption, not measured size scaling.
    def cost(size, condition):
        if condition == "all_messages_5KiB_idle":
            return p87["hidden/idle"]["total_us"]["median"] / 1000
        if condition == "production_5KiB_proxy":
            legs = transfers[TAGS[1]]
            return (legs["hidden-export/host_us/5120"]["median_us"] +
                    legs["hidden-import/host_us/5120"]["median_us"]) / 1000
        label = "hidden" if size <= 5120 else "pipeline20480"
        mult = 1 if size <= 20480 else (size + 20479)//20480
        return mult * p87[label + "/" + condition]["total_us"]["median"] / 1000
    scenarios = {}
    for condition in ["all_messages_5KiB_idle", "idle", "compute", "production_5KiB_proxy"]:
        data = []
        for name, n, total, size, send, ret in islands:
            call = total / n
            exchange = cost(send, condition) + cost(ret, condition)
            # Grant perfect row scaling, full overlap of both transport legs
            # with local rows, no assembly/dispatch cost, rank1 instantly free.
            # min_f max((1-f)*call, f*call+exchange).
            f = max(0., (1 - exchange/call)/2)
            data.append({"name": name, "calls": n, "proxy_ms": total,
                         "send_bytes": send, "return_bytes_at_half_rows": ret,
                         "roundtrip_ms_per_call": exchange, "fraction": f,
                         "weight_bytes": size*f, "cut_ms": total*f})
        # Fractional knapsack is an optimistic relaxation of a real fixed-row
        # layout; no alignment or scratch cost, fixed transaction costs already
        # paid, per-layer variation ignored. Full unfunded total also reported.
        available = margin
        saved = 0.
        used = 0.
        for r in sorted(data, key=lambda x: x["cut_ms"]/x["weight_bytes"] if x["weight_bytes"] else 0, reverse=True):
            take = min(1., available/r["weight_bytes"]) if r["weight_bytes"] else 0.
            r["admitted_fraction_of_islands"] = take
            saved += take*r["cut_ms"]
            used += take*r["weight_bytes"]
            available -= take*r["weight_bytes"]
        scenarios[condition] = {"islands": data, "unfunded_cut_ms": sum(r["cut_ms"] for r in data),
                               "weight_only_fit_bytes": used, "cut_ms": saved,
                               "gain_percent": gain(saved), "projected_tok_s": rate(saved)}
    result["row_split_sensitivities"] = scenarios
    # A more generous head-chain envelope: move whole GDN heads, including
    # recurrence, and whole QSA query heads. State/KV coherence and all its
    # storage are FREE here; this cannot qualify an implementation.
    head_total = t("attention/gdn.qkv", "attention/gdn.z", "attention/gdn.a",
                   "attention/gdn.conv", "attention/gdn.recurrence", "attention/gdn.gated")
    head_weights = w("attn_qkv.weight", "attn_gate.weight", "ssm_alpha.weight",
                     "ssm_beta.weight", "ssm_conv1d.weight", "ssm_a", "ssm_dt.bias", "ssm_norm.weight")
    free_state = {}
    for condition in ["all_messages_5KiB_idle", "idle"]:
        candidates = [dict(r) for r in scenarios[condition]["islands"] if r["name"] != "GDN qkv+z"]
        exchange = cost(5120, condition) + cost(6144, condition)
        f = max(0, (1-exchange/(head_total/18))/2)
        candidates.append({"name": "GDN whole heads", "cut_ms": f*head_total, "weight_bytes": f*head_weights})
        qsa = t("attention/qsa.attention")
        exchange_qsa = cost(12288, condition) + cost(6144, condition)
        fq = max(0, (1-exchange_qsa/(qsa/6))/2)
        candidates.append({"name": "QSA heads with free KV", "cut_ms": fq*qsa, "weight_bytes": 0})
        available = margin
        saved = 0.
        for item in sorted(candidates, key=lambda x: x["cut_ms"]/x["weight_bytes"] if x["weight_bytes"] else float("inf"), reverse=True):
            take = min(1., available/item["weight_bytes"]) if item["weight_bytes"] else 1.
            saved += take*item["cut_ms"]
            available -= take*item["weight_bytes"]
        free_state[condition] = {"cut_ms": saved, "gain_percent": gain(saved),
                                 "GDN_head_cut_ms": f*head_total, "QSA_head_cut_ms": fq*qsa,
                                 "qualification": "no: zero-cost state/KV coherence is unsupported"}
    result["head_chain_free_coherence_sensitivity"] = free_state
    # All ten current experts, half of each output row bank: actual census
    # sizes, 512 experts, no selected-route read and no hypothetical cache hit.
    stream_bytes = expert_bytes/512*10/2
    result["stream_half_selected_experts"] = {
        "bytes_per_miss": stream_bytes, "mean_bytes_per_layer": stream_bytes/24,
        "assumed_end_to_end_GBs_copy_ms": {str(bw): stream_bytes/(bw*1e6) for bw in [20,40,80]},
        "perfect_half_expert_GEMV_cut_before_transfers_ms": t("moe_experts/expsgate", "moe_experts/expsdown")/2,
        "qualification": "bulk PCIe/peer service unmeasured; assumptions are sensitivities only"}
    # Even free lossless batching of future A must finish current C before B.
    # Here a barrier waits for both causal rows; V2 proportional to C is only
    # a sensitivity, NOT the old two-card/one-card M2 measurement transferred.
    paired = {}
    for ratio in [1., 1.2, 1.700307]:
        def pair_interval(r):
            if r["hit"]:
                return interval(r)
            return max(r["D"], r["R"] + ratio*r["C"]) + r["B"] + r["unresolved_control_gaps_ms"]
        value = balanced((cls, 99000/sum(pair_interval(r) for r in rr)) for cls, rr in requests)
        paired[str(ratio)] = {"projected_tok_s": value, "gain_percent": 100*(value/base-1)}
    result["causal_pair_barrier_sensitivities"] = paired
    # B includes split-head suffix waits. Earlier A can indirectly shorten B;
    # a fixed-B counterfactual must not be called a universal graph bound.
    # Grant the old instrumented miss wait for free as an explicitly unmatched
    # sensitivity, with free second-row compute and no new memory/copy costs.
    suffix_credit = 1.468740
    pair_with_suffix = balanced((cls, 99000/sum(
        interval(r) if r["hit"] else max(r["D"], r["R"]+r["C"])+r["B"]-suffix_credit+r["unresolved_control_gaps_ms"]
        for r in rr)) for cls, rr in requests)
    result["causal_pair_free_row_and_diagnostic_suffix_credit"] = {
        "assumed_B_cut_ms_on_misses": suffix_credit,
        "projected_tok_s": pair_with_suffix,
        "gain_percent": 100*(pair_with_suffix/base-1),
        "qualification": "unmatched diagnostic suffix wait; not an ordinary-run removable budget"}
    return result


def main():
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert not (args.capture and args.check)
    if args.capture:
        capture()
    result = calculate()
    rendered = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    if args.check:
        assert (HERE / "analysis.json").read_bytes() == rendered
    else:
        (HERE / "analysis.json").write_bytes(rendered)
    print(json.dumps({"check": args.check, "record": result["record"],
                      "row_scenarios": {k: {x: v[x] for x in ["cut_ms", "gain_percent", "weight_only_fit_bytes"]}
                                        for k, v in result["row_split_sensitivities"].items()},
                      "pair_scenarios": result["causal_pair_barrier_sensitivities"],
                      "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}, indent=2))


if __name__ == "__main__":
    main()
