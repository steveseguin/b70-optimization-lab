# Recursive draft guesses on the current F32 engine — October 25

The draft guessed the second token correctly **73.09%** of the time when its
first guess was right, and the third correctly **72.25%** when its first two
guesses were right. Complete two-token guesses succeeded **55.65%** of the time;
complete three-token guesses succeeded **40.23%**. These are measured proposal
acceptance rates, not a four-card speed result.

All **5,965 output tokens across 12 prompts** match the retained
`297b388764e9` GPU baseline exactly. All 12 output-text hashes also match.
Every one of the **5,965 probe cycles** passed the byte check after restoring
the draft's mutable state. The extra proposals were discarded; the unchanged
target verified the emitted tokens. This does not resolve the six previously
reported disagreements with the independent CPU reference.

The [structured summary](depth-suite-a/depth-summary.json) contains per-prompt
counts, source hashes, timing scope, and startup/closure receipts. Each prompt
directory under [depth-suite-a](depth-suite-a/) retains its native controller
result, exact prompt IDs, HTTP response, original partial trace, completed
filtered trace, and `depth-analysis.json`.

| Depth | Correct / eligible after preceding correct guesses | Conditional acceptance | Correct complete prefix / all observable positions | Complete-prefix acceptance | End-censored positions |
|---|---:|---:|---:|---:|---:|
| 1 | 4,542 / 5,965 | 76.14% | 4,542 / 5,965 | 76.14% | 0 |
| 2 | 3,313 / 4,533 | 73.09% | 3,313 / 5,953 | 55.65% | 12 |
| 3 | 2,390 / 3,308 | 72.25% | 2,390 / 5,941 | 40.23% | 24 |

The remaining depth-2 positions include 1,420 rejected earlier guesses; depth 3
includes 2,633. No proposal depth was unavailable. End positions with no next
emitted token are censored before eligibility is counted. Rates pool actual
counts across prompts; they are neither averages of prompt percentages nor a
product of conditional rates with different denominators. Depth 1 includes the
proposal for the first output token, so its denominator differs from the service's
counter of speculative transitions after emitted tokens.

The extra draft passes averaged **1.987 ms** for depth 2 and **1.981 ms** for
depth 3, weighted by actual cycles. Snapshot time averaged 0.423 ms. Restoration
with the diagnostic byte check averaged 9.877 ms; the complete probe averaged
14.269 ms. The checks deliberately add substantial work, so this run's decode
rate is not a serving benchmark. These costs do not predict a future pipeline's
verification, rollback, communication, or overlap costs.

## Identity and closure

- Binary: `c13fae74c18433056b720b3d5bf1fb806637df0708eb98e17439e33632cf5305`.
- Model: SC117 Qwen3.8 Flash-Next IQ3_S; F32 activations, target cache and
  recurrent state; the retained [plan](depth-suite-a/plan.json) carries the
  complete two-card configuration and source identities.
- Probe flags: `OWNRT_DRAFT_DEPTH_PROBE=3`,
  `OWNRT_DRAFT_DEPTH_VERIFY=1`, `OWNRT_EARLY_RANK1=0`.
- Fixed 12-prompt suite, greedy, 512-token response cap; one response ends at
  333 tokens. Every captured HTTP response explicitly reports zero reused
  prompt tokens.
- Startup: self-test and batched-prefill gate passed; the split-aware F32
  state comparison reports no differences on either rank. Copies of those
  receipts are in [closure](depth-suite-a/closure/).
- The service drained at **17:52:28 UTC** after 39 requests including startup
  gates. Its [terminal receipt](depth-suite-a/closure/terminal.json) reports
  zero restarts, kills, retries, or errors. The monitor reports no fault and
  zero inconclusive observations.

The final cumulative trace was read from
`/dev/shm/sc117-lan-evidence/run-20261025T174204Z/rank0/draft-depth-probe.jsonl`
after closure. Its full path, size and SHA256 are recorded in the summary.
Only the exact suite request identities were extracted; startup probe rows do
not enter these counts. The completed per-prompt traces total 2,949,559 bytes,
without duplicating the whole cumulative trace for every prompt. Partial
captures remain unchanged and were verified to be prefixes of their completed
traces.

## Re-analysis and next decision

[finalize_depth_probe.py](finalize_depth_probe.py) performed the extraction and
called [analyze_draft_depth.py](../../engine/tools/analyze_draft_depth.py) with
`require_verified=True` for every prompt. The analyzer checks complete position
coverage, joins each first guess to its controller row, validates the confirmed
prefix against output IDs, and checks restoration evidence. Re-analyze a
retained prompt independently with:

```bash
python3 -B experiments/own-xpu-runtime/engine/tools/analyze_draft_depth.py \
  --prompt-ids PROMPT_DIRECTORY/prompt-token-ids.json \
  --native-result PROMPT_DIRECTORY/rank0/native-result.json \
  --probes PROMPT_DIRECTORY/rank0/draft-depth-probe-final.jsonl \
  --require-verified --output NEW_ANALYSIS.json
```

Recursive guesses are useful often enough to justify measuring a four-stage
schedule. That conclusion is an engineering inference, not a promised speedup.
The next gate is exact target-only execution across four stages, followed by a
costed speculative schedule using these measured prefix rates. Preserve the
older depth-two loss: its verification and draft-feedback structure cost more
than its extra acceptance saved. A new implementation must demonstrate lower
total time, with the same target outputs, on the complete suite.
