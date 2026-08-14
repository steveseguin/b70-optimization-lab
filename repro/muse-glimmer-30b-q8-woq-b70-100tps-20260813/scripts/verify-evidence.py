#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import statistics

root = Path(__file__).resolve().parent.parent
expected_hashes = {
    "canonical-full256-two-runs.jsonl": "01127b8d9d5659a7e4b5804e8b1980df2ab307f662e08297ab73923df6690556",
    "canonical-server-run2.log": "8951e7be05383ca04403bbc5427078faf5427e5e59f4fe65d96212142cae0914",
    "realistic-suite-result.json": "c7921dff022ec2b8d8dc87c454e8301c6c70a53b7af3f9bfca467075e0a18515",
    "realistic-server.log": "5dd371012411bcbc86066885c50012f3e7e4fba50ef1ff39cdfac8cade2f5092",
    "argmax-parity256.json": "71ea1edd2b7d59329b80d80ca7cc715da3292f9d042a0797d2f52e3d4acc8d40",
    "topk-parity256.json": "d6ff600de1dfdf90de91829b8bd61b4081c3022de320f4f25bbd0eb9d37f9923",
    "topk-parity512.json": "6773f58f46b37793e74be00c3e21d4ca9f0fd22f020886955270cdec2e31e30e",
    "code-parity1024.json": "f10abec9ca7a817abce53a1cd32acc3d2655e24c163d6ed5277248887a46e89a",
}

for name, expected in expected_hashes.items():
    path = root / "evidence" / name
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"{name}: hash mismatch: {actual}")

rows = [json.loads(line) for line in (root / "evidence/canonical-full256-two-runs.jsonl").read_text().splitlines()]
if len(rows) != 2:
    raise SystemExit("canonical evidence must contain two runs")
means = []
for row in rows:
    if any(row["prompts"][name]["predicted_n"] != 256 for name in ("prose", "code", "json")):
        raise SystemExit("canonical token count mismatch")
    mean = statistics.fmean(row["prompts"][name]["gen_tok_s"] for name in ("prose", "code", "json"))
    if mean <= 100:
        raise SystemExit(f"canonical run failed century gate: {mean}")
    means.append(mean)

realistic = json.loads((root / "evidence/realistic-suite-result.json").read_text())
metric = realistic["summary"]["tok_s_1_100_intervals_after_ttft"]
if metric["count"] != 15 or metric["median"] <= 100 or metric["p10"] <= 100:
    raise SystemExit("realistic speed gate failed")
if not realistic["realistic_final_gate"]["cached_tokens_all_zero"]:
    raise SystemExit("realistic cache-zero gate failed")

argmax = json.loads((root / "evidence/argmax-parity256.json").read_text())
classification = {row["prompt"]: row["token_exact"] for row in argmax["rows"]}
if classification != {"prose": False, "code": True, "json": True}:
    raise SystemExit(f"unexpected ARGMAX parity classification: {classification}")
topk = json.loads((root / "evidence/topk-parity256.json").read_text())
if not all(row["token_exact"] and row["content_exact"] for row in topk["rows"]):
    raise SystemExit("TOP_K 256 reference parity failed")
code = json.loads((root / "evidence/code-parity1024.json").read_text())
if not all(row["token_exact"] and row["content_exact"] for row in code["rows"]):
    raise SystemExit("code 1024 parity failed")

log_text = (root / "evidence/canonical-server-run2.log").read_text(errors="replace")
if "[spec-prof]" not in log_text:
    raise SystemExit("canonical log does not prove profiler presence")

print(json.dumps({
    "status": "PASS",
    "canonical_run_means_tok_s": means,
    "canonical_pooled_mean_tok_s": statistics.fmean(means),
    "realistic_first100_interval_median_tok_s": metric["median"],
    "realistic_first100_interval_p10_tok_s": metric["p10"],
    "realistic_cached_tokens_all_zero": True,
    "argmax_parity": classification,
    "canonical_profiler_effective": True,
}, indent=2))
