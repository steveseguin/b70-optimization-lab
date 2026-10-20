#!/usr/bin/env python3
"""Rebuild the public observation table from retained native receipts; CPU only."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).with_name("ownrt-measurements-20261019.json")
BASE = "experiments/own-xpu-runtime/stage2/packet165-warm-prefill"
SOURCES = {
    "one-card": [f"{BASE}/one-card/evidence/device-p165c-warm512-A-{r}/bracket-summary.json" for r in "ab"],
    "two-card": [f"{BASE}/two-card/evidence/device-warm512-B-{r}/bracket-summary.json" for r in "ab"],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract():
    profiles = []
    for topology, paths in SOURCES.items():
        identity_path = f"{BASE}/{topology}/identity.json"
        identity = json.loads((ROOT / identity_path).read_text())
        rows = []
        prior = None
        for path in paths:
            d = json.loads((ROOT / path).read_text())
            assert d["identity"] == identity
            assert d["passed"] is True and d["realistic_final_gate"]["passed"] is True
            assert d["submission_eligible"] is False
            assert d["quality"]["no_quality_loss_decision"] is False
            assert d["quality"]["all_available_oracle_tokens_exact"] is True
            assert d["quality"]["full_output_oracle_exact"] is False
            prefill = d["prefill"]
            assert prefill["input_tokens"] == 512 and prefill["cached_tokens"] == 0
            assert prefill["oracle_covered"] is False
            assert abs(prefill["tok_s"] - 512000 / prefill["elapsed_ms"]) < 1e-10
            assert len(d["requests"]) == 12
            classes = {}
            for request in d["requests"]:
                assert request["cached_tokens"] == 0 and request["requested_max_new"] == 512
                times = request["token_timestamps"]
                assert len(times) >= 100 and all(a < b for a, b in zip(times, times[1:]))
                rate = 99 / (times[99] - times[0])
                assert abs(rate - request["tok_s_1_100_intervals_after_ttft"]) < 1e-8
                classes.setdefault(request["prompt_class"], []).append(rate)
                oracle = json.loads((ROOT / BASE / topology / "lineage/oracle128" / (request["prompt_id"] + ".json")).read_text())
                assert request["tokens"][:128] == oracle["tokens"][:128]
            assert len(classes) == 6
            assert abs(median(median(v) for v in classes.values()) - d["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]) < 1e-8
            if prior is not None:
                assert [(r["prompt_token_sha256"], r["tokens"]) for r in d["requests"]] == [(r["prompt_token_sha256"], r["tokens"]) for r in prior["requests"]]
                assert d["prefill_request"]["tokens"] == prior["prefill_request"]["tokens"]
                assert d["prefill_request"]["prompt_token_sha256"] == prior["prefill_request"]["prompt_token_sha256"]
            prior = d
            rows.append({
                "evidence": path, "sha256": digest(ROOT / path),
                "decode_class_balanced_tok_s": d["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"],
                "suite_requests": len(d["requests"]), "response_cap": 512,
                "prefill_tok_s": prefill["tok_s"], "prefill_ttft_ms": prefill["elapsed_ms"],
                "prefill_prompt_loop_tok_s": prefill["native_prompt_loop_tok_s"],
                "request_start_boundary": prefill["request_start_boundary"],
                "full_natural_completion_statistics": d["full_natural_completion_statistics"],
                "quality": d["quality"],
                "fresh_load_repeat": d.get("fresh_load_repeat"),
            })
        assert rows[1]["fresh_load_repeat"]["passed"] is True
        assert rows[1]["fresh_load_repeat"]["request_count"] == 13
        profiles.append({
            "topology": topology, "identity": identity,
            "identity_evidence": identity_path, "identity_sha256": digest(ROOT / identity_path),
            "measurement_scope": "Twelve cold suite prompts and one distinct 512-input-token prompt per fresh load; two loads; one user; context allocation 4096.",
            "prefill_definition": "512 input tokens / native request TTFT seconds; warm runtime, cold prompt; includes first-token work; not isolated device prefill or HTTP TTFT.",
            "prefill_oracle_covered": False,
            "context_length_sweep": "not measured on this identity",
            "concurrency_sweep": "not measured; controller runs one request at a time",
            "submission_eligible": False, "rows": rows,
        })
    return {"schema": "neural.download.ownrt-observations.v1", "profiles": profiles,
            "scope": "Measured lab observations, not a promotion attestation. Exact oracle covers the first 128 output tokens only; longer outputs and the prefill response match across two fresh loads."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the derived JSON; otherwise verify it")
    args = ap.parse_args()
    expected = json.dumps(extract(), indent=2, ensure_ascii=False) + "\n"
    if args.write:
        DEST.write_text(expected)
    elif DEST.read_text() != expected:
        raise SystemExit("Observation table differs from retained evidence")
    print("PASS: two topologies, four fresh-load receipts, exact values and quality limits retained")


if __name__ == "__main__":
    main()
