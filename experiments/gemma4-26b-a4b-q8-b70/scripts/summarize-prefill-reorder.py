#!/usr/bin/env python3
"""Replay the Oct 15 second-attempt receipts without a server or GPU."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
LANE = Path("experiments/gemma4-26b-a4b-q8-b70")
DATA = LANE / "data/2026-10-15-prefill-reorder"
OUTPUT = DATA / "publication-summary.json"
PACKAGE = Path("packages/gemma4-26b-a4b-q8-b70/package.json")
PROFILE_ID = "prefill-vs-context-throughput-recipe"


def load(path):
    return json.loads((ROOT / path).read_text())


def summarize():
    sources = [DATA / "identity-check.log", DATA / "convert-change-vs-production.diff",
               LANE / "scripts/gemma-identity-check.sh",
               LANE / "notes/2026-10-15-prefill-reorder-check.md"]
    log = (ROOT / DATA / "identity-check.log").read_text()
    assert "Q8_0_REORDER_DEQ_VERIFY calls=524288 mismatched_calls=0" in log
    assert "mismatch lines: 0" in log
    for arm in ("prod-b", "new-a", "new-b", "verify"):
        assert f"suite-{arm}.json: 12/12 identical" in log
    runs = {}
    for arm in ("prod-a", "prod-b", "new-a", "new-b", "verify"):
        path = DATA / f"identity-long-{arm}.json"
        sources.append(path)
        runs[arm] = load(path)
        rows = runs[arm]["rate"]
        assert len(rows) == 6, (arm, "expected three lengths, two repeats")
        assert {(r["id"], r["rep"], r["prompt_n"]) for r in rows} == {
            (label, rep, n) for label, n in
            (("long-2k", 1867), ("long-8k", 7623), ("long-24k", 29400))
            for rep in (1, 2)
        }, (arm, "unexpected prompt/repeat identity")
        for row in rows:
            assert row["prompt_ms"] > 0
            assert math.isclose(row["prompt_per_second"],
                                row["prompt_n"] * 1000 / row["prompt_ms"], rel_tol=1e-12)
    reference = runs["prod-a"]["long"]
    assert len(reference) == 3 and all(row["tokens"] for row in reference)
    for arm, run in runs.items():
        assert run["long"] == reference, (arm, "long token parity failed")
    suites = {}
    for arm in ("prod-a", "new-a"):
        path = DATA / f"suite-{arm}.json"
        sources.append(path)
        suites[arm] = load(path)
        assert len(suites[arm]["rows"]) == 12
        assert all(r["cached_tokens"] == 0 and r["token_ids"] for r in suites[arm]["rows"])
    def tokens(suite):
        return {r["prompt_id"]: (r["prompt_sha256"], r["token_ids"]) for r in suite["rows"]}
    assert len(tokens(suites["prod-a"])) == 12
    assert tokens(suites["prod-a"]) == tokens(suites["new-a"]), "suite token parity failed"

    arms = {}
    for label in ("prod", "new"):
        points = []
        for n in (1867, 7623, 29400):
            observations = [dict(server=arm, **r) for arm in (label + "-a", label + "-b")
                            for r in runs[arm]["rate"] if r["prompt_n"] == n]
            rates = [r["prompt_per_second"] for r in observations]
            points.append({"context_tokens": n, "value": mean(rates), "samples": len(rates),
                           "min": min(rates), "max": max(rates), "observations": observations})
        arms[label] = points
    return {
        "format": "neural.download.gemma-prefill-reorder-summary.v1",
        "source_attempt": "2026-10-15 second attempt, 19:26–20:03 EDT",
        "metric": "Server prompt_n * 1000 / prompt_ms; arithmetic mean of four request rates per point",
        "controls": {
            "target": "Gemma 4 26B A4B UD-Q8_K_XL", "runtime": "llama.cpp c926 production compatibility build",
            "host": "steve-TURIND8-2L2T", "measuring_card": 1, "cards_used_by_test": 1,
            "other_host_work": "Gemma LAN service on card 0", "context_tokens": 32768,
            "parallel": 1, "kv_type": "f16", "speculation": "off",
            "GGML_SYCL_DNNL_DETERMINISTIC": "1", "LLAMA_PREFILL_UBATCH_SIZE": "1024",
            "temperature": 0, "timed_request_output_cap": 1,
            "cache_policy": "cache_prompt=false per request; cache-ram=0; ctx-checkpoints=0",
            "workload": "Same three diagnostic long prompts repeated twice per server after suite and long-output checks",
            "headlining": False,
        },
        "production": arms["prod"],
        "candidate_not_shipped": {
            "points": arms["new"],
            "gain_percent": [100 * (b["value"] / a["value"] - 1)
                             for a, b in zip(arms["prod"], arms["new"])],
            "flag": "LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED=1",
            "reproducible_build_identity_closed": False,
            "missing": ["Full test-build server and shared-library hashes (note retains prefixes only)",
                        "Exact production compatibility source/toolchain/build receipt to which the delta applied",
                        "Tracked long prompt inputs; historical runner names a host-only JSON path",
                        "Clean rebuild and full-gate replay of the separately declared candidate profile"],
        },
        "quality": {
            "long_token_comparisons_replayed": "prod-b, new-a, new-b, verify each equal prod-a: 3/3",
            "suite_token_comparison_replayed": "new-a equals prod-a: 12/12, identical prompt hashes",
            "suite_comparisons_retained_only_in_log": "prod-b, new-b, verify equal prod-a: 12/12 each",
            "conversion_check_retained_only_in_log": "524288 calls, 0 mismatched calls, 0 mismatch lines",
            "scope": "Token parity for tested prompts; not a general mathematical proof or a new headline attestation",
        },
        "sources": [{"path": str(p), "sha256": hashlib.sha256((ROOT / p).read_bytes()).hexdigest()}
                    for p in sources],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write only the derived evidence summary")
    args = parser.parse_args()
    result = summarize()
    if args.write:
        (ROOT / OUTPUT).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    else:
        assert load(OUTPUT) == result, "summary drift; inspect receipts before regenerating with --write"
        profile = next(p for p in load(PACKAGE)["performance_profiles"] if p["id"] == PROFILE_ID)
        expected = [{k: p[k] for k in ("context_tokens", "value", "samples")} for p in result["production"]]
        assert profile["points"] == expected, "package points differ from production receipts"
        assert profile["evidence"] == str(OUTPUT)
    print("PASS: exact timing formulas, repeat identities, retained token parity, and production aggregates")


if __name__ == "__main__":
    main()
