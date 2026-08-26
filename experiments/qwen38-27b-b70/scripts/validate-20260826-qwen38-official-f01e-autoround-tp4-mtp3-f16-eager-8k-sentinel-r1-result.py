#!/usr/bin/env python3
"""Read-only validator for the published current-f01e TP4/MTP3 sentinel."""
import argparse, hashlib, json, math
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp4-mtp3-f16-eager-8k-sentinel-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp3-f16-eager-8k-sentinel-r1-result.json"

def load(path): return json.loads(path.read_text())
def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 << 20), b""): h.update(chunk)
    return h.hexdigest()
def need(value, message):
    if not value: raise RuntimeError(message)

def validate(root, result_path):
    r = load(result_path)
    need(r["status"] == "passed-quality-clean-sentinel", "result not passed")
    for binding in r["tracked_inputs"].values():
        path = REPO / binding["path"]; need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")
    for name, expected in r["identity"]["raw_sha256"].items(): need(digest(root / name) == expected, f"identity changed: {name}")
    inspect = load(root / "container-inspect.json")[0]; args, env = inspect["Config"]["Cmd"], inspect["Config"]["Env"]
    arg = lambda name: args[args.index(name) + 1]
    need(arg("--tensor-parallel-size") == "4" and arg("--gpu-memory-utilization") == "0.60", "TP4 identity changed")
    need("--enforce-eager" in args and "--kv-cache-dtype" not in args and "--compilation-config" not in args, "eager/F16 changed")
    need(json.loads(arg("--speculative-config")) == {"method":"qwen3_next_mtp","num_speculative_tokens":3}, "MTP3 changed")
    need("ZE_AFFINITY_MASK=0,1,2,3" in env and not any(x.startswith("ONEAPI_DEVICE_SELECTOR=") for x in env), "GPU selection changed")
    need("VLLM_XPU_ENABLE_XPU_GRAPH=0" in env and "VLLM_XPU_GRAPH=0" in env, "graph off changed")
    terminal, cleanup = load(root / "terminal-receipt.json"), r["cleanup"]
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 0 and terminal["state"] == r["status"], "terminal not rc0")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"] and not terminal["automatic_descendant_expansion"], "terminal authority widened")
    arm = load(root / "arm-result.json"); need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm changed")
    gates = ("acceptance_conserved","acceptance_passed","cleanup_passed","objective_quality_passed","rank_cache_isolation_passed","same_topology_baseline_comparison_passed","same_topology_target_verification_passed","startup_identity_passed","tp4_worker_topology_passed")
    need(arm["runner_return_code"] == 0 and arm["exact_8k_return_code"] == 0 and arm["quality_return_code"] == 0 and all(arm[k] for k in gates), "arm gate failed")
    need(not arm["publication_authorized"] and not arm["descendant_expansion_authorized"] and not arm["descendant_execution_authorized"], "raw authority changed")
    raw_path = root / "exact-depth/depth-8192.json"; raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-8192.stdout.json") and raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), "depth gate failed")
    usage, metric = raw["response"]["usage"], raw["metric_window"]; need(usage["prompt_tokens"] == 8192 and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"]["cached_tokens"] == 0, "usage changed")
    ttft = metric["time_to_first_token_s"]
    point = {"x":8192,"decode_tok_s":metric["conventional_99_interval_tok_s"],"historical_100_event_decode_tok_s":metric["historical_100_event_tok_s"],"published_decode_field":"conventional_99_interval_tok_s","ttft_s":ttft,"ttft_ms":ttft*1000,"effective_prompt_throughput_proxy_tok_s":8192/ttft,"cached_tokens":0,"completion_tokens":128,"output_token_ids_sha256":raw["response"]["output_token_ids_sha256"],"raw_sha256":digest(raw_path)}
    need(point == r["point"], "point changed")
    vg, mech = load(root / "verification-gates.json"), r["mechanism"]; need(digest(root / "verification-gates.json") == mech["raw_sha256"], "verification changed")
    acc = vg["acceptance"]
    for key in ("before_drafted_tokens","after_drafted_tokens","drafted_tokens","before_accepted_tokens","after_accepted_tokens","accepted_tokens","acceptance_rate"): need(math.isfinite(acc[key]) and acc[key] == mech[key], f"acceptance changed: {key}")
    need(acc["passed"] and acc["conserved"], "acceptance failed")
    oracle, target = r["same_topology_oracle"], vg["target_verification"]
    need(target["passed"] and target["first_divergence"] is None and target["candidate_ids_sha256"] == target["target_ids_sha256"] == oracle["target_token_ids_sha256"], "parity failed")
    target_path, terminal_path = Path(oracle["target_path"]), Path(oracle["target_terminal_path"])
    need(digest(target_path) == oracle["target_raw_sha256"] and digest(terminal_path) == oracle["target_terminal_sha256"], "oracle changed")
    need(raw["response"]["token_ids"] == load(target_path)["response"]["token_ids"], "token parity changed")
    quality = load(root / "quality.json"); need(digest(root / "quality.json") == r["quality"]["raw_sha256"], "quality changed")
    need(quality["pass_all"] and quality["baseline_match_all"] and len(quality["exact_cases"]) == 7 and all(x["pass"] for x in quality["exact_cases"]), "quality failed")
    repeat = quality["repeat_case"]; need(repeat["pass"] and repeat["repeats"] == 8 and len(repeat["unique_hashes"]) == 1 and quality["long_context_case"]["pass"], "repeat/long failed")
    usages = [x["usage"] for x in quality["exact_cases"]] + [x["usage"] for x in repeat["runs"]] + [quality["long_context_case"]["usage"]]
    need(len(usages) == 16 and all(x["prompt_tokens_details"]["cached_tokens"] == 0 for x in usages), "cache reuse appeared")
    need(digest(root / "rank-cache-isolation.txt") == r["topology_and_cache"]["rank_cache_raw_sha256"], "rank cache changed")
    model = load(root / "model-verification.json"); need(digest(root / "model-verification.json") == r["model_verification"]["raw_sha256"] and model["status"] == "verified" and len(model["files"]) == 19 and all(x["ok"] and x["paths_coherent"] for x in model["files"]), "model verification failed")
    adj, auth = r["adjudication"], r["authority"]
    need(not adj["raw_automatic_publication_authority"] and adj["explicit_human_per_cell_publication_authority"] and adj["published_depths"] == [8192] and not adj["descendant_expansion_authorized"], "adjudication changed")
    need(auth["site_cells"] == 1 and auth["quality_grade"] == "C" and not auth["historical_or_protected_replacement"] and not auth["other_depths_tp_mtp_graph_or_kv_inferred"], "authority changed")
    need(auth["protected_decode_values_unchanged"] == [71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144], "protected changed")
    return {"status":"pass","cells_published":1,"tp":4,"mtp":3,"accepted":89,"drafted":114,"grade":"C","publication":"explicit-human-per-cell"}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,default=ROOT); p.add_argument("--result",type=Path,default=RESULT); a=p.parse_args()
    try: report=validate(a.root,a.result)
    except (KeyError,OSError,TypeError,ValueError,RuntimeError,json.JSONDecodeError) as exc: p.error(str(exc))
    print(json.dumps(report,indent=2,sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
