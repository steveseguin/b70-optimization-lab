# DRAFT — held after evidence review on 2026-09-12 (not filed)

## Disposition

Retain the historical output anomaly and reproducer. Do not submit the former
claim that an ungenerated token was inserted by bookkeeping: the R170 and R171
traces contradict it. A fresh reproduction with the exact FP8 target, current
upstream, and complete token/logit evidence is needed before deciding the
remaining issue's scope. The recorded FP8 model path is absent on the current
four-card host; no model download or GPU run was started for this review.

The original draft remains in Git history. See the
[September 12 review](../experiments/qwen38-27b-b70/upstream-review-20260912/README.md).

## Candidate title, if reconfirmed

[XPU][Spec decode] Qwen3.8-27B FP8 MTP2: intermittent anomalous first-token
prediction on sequential short requests (historical stock ac7509e2b)

## Confirmed historical observations

The September 3 stock-image summaries record one request beginning
`[60, 271, 3833, ...]` rather than `[271, 3833, ...]` on three of six fresh
servers. Token 60 decodes as `]`, which is also the last character in the
expanded prompt. One compiled async-off server affected `cache-c032`; both
eager async-on servers affected `cache-c040`. The other three stock servers
had no such leading-token anomaly. The stock image was unmodified by the lab.

These observations establish a historical configuration/history-sensitive
output discrepancy. They do not alone identify an insertion, scheduling,
compiler, kernel, or memory-race root cause, or prove it persists on current
upstream. Mid-sequence differences on stock were also common and must not
all be counted as the same anomaly.

## Correction to the original explanation

- [R170 handoff trace](../experiments/qwen38-27b-b70/data/2026-09-03-qwen38-fp8-r156-mtp2-phantom-handoff-logging-r170-result.json):
  on the instrumented lab build, the sampler returned `sampled_token_ids=[[60]]`;
  the host copy and scheduler faithfully appended it. The sampler's input row,
  not HTTP output insertion, was the observed source of the unexpected token.
- [R171 logit trace](../experiments/qwen38-27b-b70/data/2026-09-03-qwen38-fp8-r156-mtp2-phantom-logits-row-r171-result.json):
  `logits_indices=[30]`, query starts `[0,31]`, and row 30's top logits were
  token60/token26 at 14.82/13.95. The proposed row-index off-by-one was rejected.
- [Later R186 trace](../experiments/qwen38-27b-b70/notes/2026-09-03-qwen38-fp8-mtp2-phantom-inductor-knobs-r184-result.md):
  scalar absolute-sum signatures of the sampled final hidden row differed
  between TP ranks on the affected request; these were not complete tensor
  comparisons. That supports investigation of forward-state corruption, but the
  exact faulting operation was not identified. A token220 variant also occurred,
  so checking only for token60 is not a complete detector.

Those instrumented lab-build traces must not be represented as instrumented
stock-upstream traces. The stock evidence is the separate R192/R194 campaign.

## Historical environment and runnable inputs

- vLLM `0.27.2rc1.dev77+gac7509e2b`, torch `2.13.0+xpu`, two Intel Arc Pro B70s,
  Ubuntu 24.04.
- Stock image:
  `vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`.
- Model: `Qwen/Qwen3.8-27B-FP8`, native FP8 weights, FP16 activations/KV,
  TP2, `qwen3_next_mtp` with `num_speculative_tokens=2`.
- Maximum model length256, block size64, maximum sequences64, batched tokens512,
  prefix caching disabled. Greedy completions, seed42, 128 output tokens,
  `ignore_eos=true`, raw token IDs requested.
- Exact base prompts:
  [small-context suite](../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json).
  The [concurrency harness](../scripts/bench-openai-concurrency-oracle.py) expands
  eight prompts into 64 in order by appending
  `\n\n[Independent validation case {index:03d}; variant {index // 8:02d}]`.
  The affected observations are from its initial sequential oracle pass, not
  the later concurrent batch.
- Complete historical launch identity:
  [R192 runner](../experiments/qwen38-27b-b70/scripts/run-20260903-stock-vllm-f01e-mtp2-phantom-r192.sh),
  [R194 runner](../experiments/qwen38-27b-b70/scripts/run-20260903-stock-vllm-f01e-mtp2-phantom-repeats-r194.sh).
  These are archival host-specific runners, not safe generic launch commands.

## Results and downstream handling

- [R192 JSON](../experiments/qwen38-27b-b70/data/2026-09-03-qwen38-stock-f01e-mtp2-phantom-r192-result.json)
- [R194 JSON](../experiments/qwen38-27b-b70/data/2026-09-03-qwen38-stock-f01e-mtp2-phantom-repeats-r194-result.json)
- [Stock campaign note](../experiments/qwen38-27b-b70/notes/2026-09-03-qwen38-stock-f01e-mtp2-phantom-r192-result.md)

The lab's published R187 configuration uses `splitting_ops=[]`, which avoided
the observed anomaly on that deterministic build. It is a scoped workaround,
not a generally validated root-cause fix. The later one-token GDN phase bug and
variable speculative-width kernel contract are separate findings; neither is
established as this anomaly's cause.

## Gate before filing

Restore and verify the target and exact launch identity on an available host;
reproduce stock control first, then current upstream on the same prompt order;
retain complete outputs and sampled logits/indices around the affected first
step. Compare related accepted-count ordering fixes only when their specific
preconditions apply. Report the observed forward discrepancy without claiming
an unproven mechanism. Do not treat a clean small pass as proof of absence.
