# Exact-Q4 DFlash adaptation capture gate

Date: 2026-07-13 UTC

## Outcome

No adapter training was launched. The existing
`qwen36_eagle_sequence_v2` traces fail the active-product identity gate: their
target features and greedy continuations came from the Webhie AutoRound INT4
vLLM target, while the current product target is the GGUF Q4_0 model with
SHA-256
`20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a`.

This is not a prompt-leakage failure. The retained v6b corpus has 384 generated
engineering prompts, requests `enable_thinking=false`, uses 12 families, and
has zero exact prompt-hash overlap with the fixed 12-prompt benchmark. Shards
0..2 contain 288 prompts across nine training families; shard 3 contains 96
prompts across three held-out families, with no family overlap.

It is a target-label failure. Q4_0 can change greedy continuation IDs and every
target layer-input feature row. A candidate trained against AutoRound labels
cannot satisfy the requested exact active-Q4 screening result, even though the
target would eventually reject incorrect draft tokens.

## Existing adaptation evidence

`scripts/train-qwen27-dflash-offline.py` already implements the relevant
small-scope boundaries and a paired held-out evaluator. The analysis script
`scripts/analyze-qwen27-dflash-adaptation.py` clusters the exploratory effect
at family-by-task scenario level and warns that the held-out corpus has been
adaptively inspected.

Prior AutoRound-target screens establish a strong early-stop prior:

| scope | trainable size at prior B=5 | best visible-token lift | result |
|---|---:|---:|---|
| layer target fusion | 25 | +0.0230 | too small |
| layer position bias | 128,000 | +0.0664 | smallest clear positive |
| layer/position query LoRA rank 32 | about 8.2M | +0.1006 | positive, too small |
| layer/position query LoRA rank 64 | about 16.4M | +0.1299 | best query LoRA, too small |
| separate context K/V | about 52.4M | +0.0957 | plateaued, too small |

For an exact-Q4 B=6 screen, layer position bias is the selected first scope. Its
shape is five draft layers by six block positions by hidden width 5120, or
153,600 zero-initialized parameters. It is algebraically identical to the
source checkpoint before the first update. The smallest LoRA escalation is
rank-32 layer/position query LoRA.

The hard gate remains at least `4.0` mean accepted drafts / `5.0` visible
tokens per B=6 cycle on family-disjoint held-out data. Stop after the first two
held-out checkpoints if visible depth remains below `3.5` and the second
checkpoint gains less than `0.10`. The prior effects are an order of magnitude
below the required lift; a statistically nonzero result is not enough.

## Implemented capture plan

New identity gate:

```text
scripts/prepare-qwen27-dflash-q4-capture.py
```

It validates:

- the existing collector model identity;
- exact suite/benchmark prompt-hash disjointness;
- train/held-out family disjointness;
- active target and draft model identities;
- llama.cpp commit and dirty-patch SHA-256;
- presence of the required native target-feature hook;
- the selected adapter scope and hard early-stop gate.

The generated plan is:

```text
data/qwen27-dflash-q4-adaptation-capture-20260713/capture-plan.json
```

Its SHA-256 is
`e8c619ab8ce64994cffd12ba067521b88cfbfa254583b9572820b474028426de`.

The plan exits with status 2 and `training_authorized=false` while either the
target identity or native hook is missing. It records the current protected
runtime identity without modifying it.

New fail-closed collector:

```text
scripts/collect-qwen27-dflash-q4-training-corpus.py
```

Before sending a single prompt, it requires a server-written
`qwen27_dflash_native_capture_session_v1` manifest and verifies:

- exact Q4 target and Q8 draft SHA-256 values;
- exact llama.cpp commit and dirty-patch SHA-256;
- reasoning off and prompt cache disabled;
- DFlash `n_max=0`, `n_min=0`, and `p_min=0`;
- F16 draft K/V;
- target layer-input indices `[2,17,32,47,62]`;
- an active native capture hook and absolute capture directory.

For each sequential request, it then requires an atomically completed
`qwen27_dflash_native_target_trace_v1` metadata record, aligned token/position
arrays, `[tokens,5,5120]` target features, and a checksum-valid payload. Any
identity or alignment mismatch aborts collection.

## Why capture with DFlash n_max=0

The native DFlash driver already enables extraction of the five target layer
inputs and gathers them into `features_buf`. In ordinary speculative mode the
target verification batch also contains draft candidates; rows after the first
rejection are not the actual linear target continuation.

Launching the capture-only server with DFlash present but `n_max=0` retains the
feature extraction path while making every target decode row part of the real
linear greedy target trajectory. This avoids constructing training examples
from rejected speculative branches. It is an offline corpus collection mode,
not a throughput configuration.

## Remaining blocker

The protected llama.cpp source currently exposes
`LLAMA_DFLASH_LMHEAD_CAPTURE`, which captures final normalized DFlash decoder
rows for the LM-head experiment. It does not capture target layer inputs,
linear target token IDs, positions, or prompt/generation boundaries. No
`LLAMA_DFLASH_TARGET_TRACE_CAPTURE_DIR` hook exists.

The missing hook must be implemented in a separate non-protected worktree and
must be completely dormant without its environment variable. It should publish
the session manifest at server startup and per-request trace/payload pairs by
atomic rename. After same-build validation, use GPU0 for the 288/96 exact-Q4
capture and the bounded layer-position-bias screen. GPU3 and the protected
active server were not touched during this audit.

This capture plan, its future corpus, and any adapter screen are diagnostic and
not LocalMaxxing eligible. Only a target-verified cold fixed-suite decode record
can be submitted.
