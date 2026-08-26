#!/usr/bin/env python3
"""Read-only validator for the TP4/MTP4 structural quarantine."""
import argparse, hashlib, json, math
from pathlib import Path
REPO=Path(__file__).resolve().parents[3]
ROOT=Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-8k-sentinel-20260826-r1")
RESULT=REPO/"experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-8k-sentinel-r1-result.json"
def load(p): return json.loads(p.read_text())
def digest(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for c in iter(lambda:f.read(4<<20),b""): h.update(c)
 return h.hexdigest()
def need(v,m):
 if not v: raise RuntimeError(m)
def validate(root,result_path):
 r=load(result_path); need(r["status"]=="quarantined-target-parity-failed","wrong result state")
 for b in r["tracked_inputs"].values():
  p=REPO/b["path"]; need(p.is_file() and digest(p)==b["sha256"],f"tracked input changed: {p}")
 for n,e in r["identity"]["raw_sha256"].items(): need(digest(root/n)==e,f"identity changed: {n}")
 c=load(root/"container-inspect.json")[0]; args,env=c["Config"]["Cmd"],c["Config"]["Env"]; arg=lambda n:args[args.index(n)+1]
 need(arg("--tensor-parallel-size")=="4" and arg("--gpu-memory-utilization")=="0.60","TP4 changed")
 need("--enforce-eager" in args and "--kv-cache-dtype" not in args and "--compilation-config" not in args,"eager/F16 changed")
 need(json.loads(arg("--speculative-config"))=={"method":"qwen3_next_mtp","num_speculative_tokens":4},"MTP4 changed")
 need("ZE_AFFINITY_MASK=0,1,2,3" in env and not any(x.startswith("ONEAPI_DEVICE_SELECTOR=") for x in env),"GPU selection changed")
 terminal=load(root/"terminal-receipt.json"); need(digest(root/"terminal-receipt.json")==r["cleanup"]["terminal_receipt_sha256"],"terminal changed")
 need(terminal["terminal"] and terminal["runner_return_code"]==39 and terminal["state"]==r["status"],"terminal not quarantined rc39")
 need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"] and not terminal["automatic_descendant_expansion"],"terminal authority widened")
 arm=load(root/"arm-result.json"); need(digest(root/"arm-result.json")==r["cleanup"]["arm_result_sha256"],"arm changed")
 passed=("acceptance_conserved","acceptance_passed","cleanup_passed","objective_quality_passed","rank_cache_isolation_passed","same_topology_baseline_comparison_passed","startup_identity_passed","tp4_worker_topology_passed")
 need(arm["runner_return_code"]==39 and arm["exact_8k_return_code"]==0 and arm["quality_return_code"]==0 and all(arm[k] for k in passed),"non-parity gate failed")
 need(not arm["same_topology_target_verification_passed"] and arm["lower_grade_evidence_retained"],"quarantine cause changed")
 need(not arm["publication_authorized"] and not arm["descendant_expansion_authorized"] and not arm["descendant_execution_authorized"],"raw authority widened")
 raw_path=root/"exact-depth/depth-8192.json"; raw=load(raw_path); need(raw==load(root/"exact-depth/depth-8192.stdout.json") and raw["gate"]["passed"] and all(raw["gate"]["checks"].values()),"exact depth failed")
 u=raw["response"]["usage"]; need(u["prompt_tokens"]==8192 and u["completion_tokens"]==128 and u["prompt_tokens_details"]["cached_tokens"]==0,"usage changed")
 d=r["diagnostic_point"]; m=raw["metric_window"]
 need(d["raw_sha256"]==digest(raw_path) and d["historical_100_event_decode_tok_s"]==m["historical_100_event_tok_s"] and d["conventional_99_interval_decode_tok_s"]==m["conventional_99_interval_tok_s"] and d["ttft_s"]==m["time_to_first_token_s"],"diagnostic timing changed")
 need(not d["site_speed_publication"] and not d["headline_authority"],"diagnostic speed authority appeared")
 vg=load(root/"verification-gates.json"); need(digest(root/"verification-gates.json")==r["mechanism"]["raw_sha256"],"verification changed")
 a=vg["acceptance"]
 for k in ("before_drafted_tokens","after_drafted_tokens","drafted_tokens","before_accepted_tokens","after_accepted_tokens","accepted_tokens","acceptance_rate"): need(math.isfinite(a[k]) and a[k]==r["mechanism"][k],f"acceptance changed: {k}")
 need(a["passed"] and a["conserved"],"acceptance failed")
 t,expected=vg["target_verification"],r["target_failure"]
 need(not t["passed"] and t["candidate_ids_sha256"]==expected["candidate_token_ids_sha256"] and t["target_ids_sha256"]==expected["target_token_ids_sha256"],"target failure changed")
 need(t["first_divergence"]==expected["first_divergence"] and t["first_divergence"]["one_based"]==99,"divergence changed")
 need(digest(Path(expected["target_path"]))==expected["target_raw_sha256"],"target oracle changed")
 q=load(root/"quality.json"); need(digest(root/"quality.json")==r["quality"]["raw_sha256"] and q["pass_all"] and q["baseline_match_all"],"quality changed")
 repeat=q["repeat_case"]; usages=[x["usage"] for x in q["exact_cases"]]+[x["usage"] for x in repeat["runs"]]+[q["long_context_case"]["usage"]]
 need(len(q["exact_cases"])==7 and repeat["pass"] and repeat["repeats"]==8 and q["long_context_case"]["pass"] and len(q["baseline_comparisons"])==24,"quality coverage changed")
 need(len(usages)==16 and all(x["prompt_tokens_details"]["cached_tokens"]==0 for x in usages),"cache reuse appeared")
 need(digest(root/"rank-cache-isolation.txt")==r["topology_and_cache"]["rank_cache_raw_sha256"],"rank cache changed")
 model=load(root/"model-verification.json"); need(digest(root/"model-verification.json")==r["model_verification"]["raw_sha256"] and model["status"]=="verified" and len(model["files"])==19 and all(x["ok"] and x["paths_coherent"] for x in model["files"]),"model verification failed")
 auth=r["authority"]; need(not auth["raw_publication_authorized"] and auth["site_structural_quarantine_cells"]==1 and auth["site_measured_speed_cells"]==0 and auth["diagnostic_speed_retained_only_in_evidence"],"site authority changed")
 need(not auth["historical_or_protected_replacement"] and not auth["other_depths_tp_mtp_graph_or_kv_inferred"] and auth["protected_decode_values_unchanged"]==[71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144],"protected/scope changed")
 return {"status":"pass","structural_quarantine_cells":1,"measured_speed_cells":0,"tp":4,"mtp":4,"divergence_token":99,"runner_rc":39}
def main():
 p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,default=ROOT); p.add_argument("--result",type=Path,default=RESULT); a=p.parse_args()
 try: report=validate(a.root,a.result)
 except (KeyError,OSError,TypeError,ValueError,RuntimeError,json.JSONDecodeError) as e: p.error(str(e))
 print(json.dumps(report,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
