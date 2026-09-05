#!/usr/bin/env python3
"""Build the promotion attestation (neural.download.promotion-attestation.v1) for a realistic-suite
result of the VRAM-headroom identity, from the approved A134 attestation as the template.

Quality evidence: the frozen client's deterministic summary (quality suite, short r1-r3, exact 2K/4K
pairs on a fresh server) and the exact-2K pair summary (A179 + A180 r1/r2 vs the authority)."""
import argparse, datetime, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "experiments/qwen38-flash-next-fp8-b70/data/20260904-tp4-mtp0-a134-promotion-attestation.json"

def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def rel(p: Path) -> str:
    return str(p.resolve().relative_to(ROOT))

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True, type=Path)
    ap.add_argument("--client-summary", required=True, type=Path, help="frozen-client deterministic summary (ple-only-qsa-stable-summary.json copy)")
    ap.add_argument("--pair-summary", required=True, type=Path, help="exact-2K pair summary across servers")
    ap.add_argument("--runtime-revision", required=True)
    ap.add_argument("--optimization-identity", required=True)
    ap.add_argument("--profile-id", required=True)
    ap.add_argument("--note", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    att = json.loads(TEMPLATE.read_text())
    res = json.loads(a.result.read_text())
    cs = json.loads(a.client_summary.read_text())
    ps = json.loads(a.pair_summary.read_text())
    assert res["realistic_final_gate"]["passed"]
    assert cs["status"] == "passed" and cs["quality"]["repeat"].endswith("one hash"), cs["quality"]
    assert cs["exact_2k"]["same_boot_output_repeat"] and cs["exact_4k"]["same_boot_output_repeat"]
    assert all(r["ids_equal_to_reference"] for r in ps["rows"]), ps
    assert cs["identity"]["vllm_head"] == a.runtime_revision
    att["created_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    att["profile_id"] = a.profile_id
    att["headline"]["value"] = res["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
    att["headline"]["note"] = a.note
    att["performance_evidence"] = {"path": rel(a.result), "sha256": sha256(a.result)}
    att["identity"]["runtime_revision"] = a.runtime_revision
    att["identity"]["optimization_identity"] = a.optimization_identity
    att["quality_evidence"] = [
        {"path": rel(a.client_summary), "sha256": sha256(a.client_summary),
         "supports": ["varied_task_quality_passed", "exact_or_target_oracle_passed", "deterministic_repeats_passed",
                      "fresh_server_repeat_passed", "target_model_unchanged", "no_quality_loss"]},
        {"path": rel(a.pair_summary), "sha256": sha256(a.pair_summary),
         "supports": ["fresh_server_repeat_passed", "deterministic_repeats_passed", "exact_or_target_oracle_passed"]},
    ]
    a.out.write_text(json.dumps(att, indent=1) + "\n")
    print("wrote", a.out, "headline", att["headline"]["value"])

if __name__ == "__main__":
    main()
