# Qwen27 Draft Oracle Trace Branch/Tail Screen

Date: 2026-07-07

Status: closed as diagnostic no-win for the simple branch/tail-rescue idea.

## Purpose

Older branch/regenerate traces could not see the actual async proposed draft
tokens because scheduler-side rows often contained `-1` placeholders. I added a
default-off worker-side trace hook after `self.propose_draft_token_ids(...)` so
we can pair real proposed draft rows with the subsequent verifier
`mamba_state_update_begin` rows.

This asks one narrow question: when the verifier rejects a draft prefix and
emits a target-owned bonus/replacement token, does that target token often
appear later in the same just-proposed draft tail? If yes, a graph-safe
branch/tail mechanism might rescue work; if no, that mechanism does not have
enough leverage.

## Trace Hook

Focused patch artifact:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-draft-oracle-trace-20260707.patch`

Runtime gates:

- `VLLM_XPU_DRAFT_ORACLE_TRACE=1`
- `VLLM_XPU_COW_WORKER_TRACE_FILE=<path>`
- `VLLM_XPU_COW_WORKER_TRACE_MAX_LINES=<n>`

Reusable summarizer:

- `scripts/summarize-qwen27-draft-oracle-trace.py`

## Run Identity

Run directory:

- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-draft-oracle-trace-20260707T111040Z`

Tracked summaries:

- `experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-draft-oracle-trace-candidate-summary-20260707.json`
- `experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-draft-oracle-trace-summary-20260707.json`
- `experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-draft-oracle-trace-summary-20260707.md`

Ignored/raw support artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draft-oracle-trace-realistic128-chat-tokenids-qwensuite-20260707T111040Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draft-oracle-trace-summary-20260707T111040Z.json`
- raw COW JSONL trace at `$RUN_DIR/draft-oracle-cow-trace.jsonl`

Config was the current Qwen27 best recipe family:

- `webhie/Qwen3.6-27B-int4-AutoRound`
- TP1, one B70
- `qwen3_next_mtp`, `NUM_SPECULATIVE_TOKENS=3`
- `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}`
- ReplaySSM exact GDN state path
- target LM-head INT8 with BF16 scales
- draft LM-head INT4 with BF16 scales
- PyTorch slot-management fallback

Strict freshness mechanics passed:

- fixed realistic Qwen suite
- 12 unique prompts, each once
- `cached_tokens=0` for every request
- prefix cache hit rate `0.0%`
- no history/ngram/cache acceleration

Quality was intentionally skipped because this was trace diagnostics only, not
a promoted benchmark candidate. Throughput was also not headline-valid because
the trace hook adds CPU synchronization and JSONL writes.

## Result

Paired rows: `2143`.

Accepted-draft histogram:

```json
{
  "0": 439,
  "1": 483,
  "2": 422,
  "3": 799
}
```

Raw visible-token histogram:

```json
{
  "1": 439,
  "2": 483,
  "3": 422,
  "4": 799
}
```

Key metrics:

- mean accepted draft tokens: `1.7377508166122257`
- mean raw visible tokens: `2.737750816612226`
- full-accept rows: `799` / `2143` = `37.284%`
- partial-reject rows: `1344` / `2143` = `62.716%`
- prefix mismatches: `0`
- bonus/replacement token appeared later in the unaccepted draft tail:
  `42` rows
- bonus-tail hit rate over all rows: `1.9599%`
- bonus-tail hit rate over partial rejects: `3.125%`

The impossible same-cost all-full MTP3 multiplier is `1.46105x`, i.e. four
visible tokens per step instead of the observed `2.73775`. This is an upper
bound and assumes zero overhead plus every verifier row full-accepts, which is
not a reachable implementation.

## Decision

Do not implement a simple branch/tail rescue path for this signal. The target
bonus token appears later in the draft tail too rarely to pay for graph-safe
fork/rollback/replay machinery.

This is consistent with the stricter branch/regenerate envelope:

- current recipe step cost is about `40 ms`;
- MTP3 maximum visible tokens per verifier step is `4`;
- at the current step cost, `100 tok/s` requires slightly more than `4` tokens
  per step;
- therefore MTP3-only branch/regenerate cannot be the main `>100 tok/s` route
  unless verifier-step cost drops materially.

The next credible `>100 tok/s` lanes are:

1. reduce verifier/LM-head cost per step;
2. increase speculation depth with a stronger legal drafter;
3. build a DFlash/EAGLE-style architecture that actually raises fresh-prompt
   acceptance depth, then make its GDN/DeltaNet state transitions exact.
