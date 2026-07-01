# 2026-07-01 Direct sampled-ID egress negative

## Goal

Try to remove the remaining sampled-token extraction/copy overhead from the
Gemma 4 26B A4B Q8 llama.cpp record stack without changing model quality,
target quantization, speculation semantics, prompt cache policy, or validation
rules.

This was aimed at the verifier/sample-output cost lane. The current valid record
remains:

- `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`
- median generated tok/s for tokens 1-100 after TTFT:
  `124.97714084813418`
- LocalMaxxing id: `cmr1u77na01k2ld01kalwzs1e`

## Patch Snapshots

The active llama.cpp source checkout is:

`/home/steve/src/llama.cpp-gemma-record-repro-c926`

Snapshots preserved in this repo:

- pre-edit stack:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-direct-sampled-egress-preedit-source.patch`
- initial direct-egress/parity implementation:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-direct-sampled-egress-parity-source.patch`
- stricter parity diagnostic state:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-direct-sampled-egress-strictparity-source.patch`

Harness metadata/pass-through was added for:

- `LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS`
- `LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_PARITY`
- `LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_SKIP_COPY`

## Runs

All runs below used the fixed realistic prompt suite, cold responses,
`cached_tokens=0`, and the same Gemma Q8 target model/quantization. These are
diagnostic smokes only, not promoted headline results.

| Label | Flags | Canary | Gate | Median tok/s | Outcome |
|---|---|---:|---|---:|---|
| `gemma4-q8-gpu0-direct-egress-parity-smoke-20260701A` | `DIRECT_SAMPLED_EGRESS=1`, original parity | 32/32 | pass | 117.394430 | False reassurance: original parity ignored `LLAMA_TOKEN_NULL` direct entries. |
| `gemma4-q8-gpu0-direct-egress-skipcopy-smoke-20260701A` | `DIRECT_SAMPLED_EGRESS=1`, `SKIP_COPY=1` | crash | fail | n/a | Sampler crashed because backend argmax fast path returned no sampled ID and logits are not exported in this mode. |
| `gemma4-q8-gpu0-direct-egress-parity2-smoke-20260701A` | `DIRECT_SAMPLED_EGRESS=1`, strict parity | 32/32 | pass | 117.017049 | Strict parity logged repeated row-0 mismatches: direct `-1`, copied sampled token valid. |

Result dirs:

- `data/gemma4-q8-gpu0-direct-egress-parity-smoke-20260701A/`
- `data/gemma4-q8-gpu0-direct-egress-skipcopy-smoke-20260701A/`
- `data/gemma4-q8-gpu0-direct-egress-parity2-smoke-20260701A/`

External server logs:

- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-direct-egress-skipcopy-smoke-20260701A.server.log`
- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-direct-egress-parity2-smoke-20260701A.server.log`

## Crash Signature

Skip-copy is unsafe in the current implementation. The server aborts during the
canary:

```text
GGML_ASSERT(logits != nullptr) failed
get_logits_ith: invalid logits id 38, reason: no logits
```

Mechanism: `common_sampler_sample()` first tries
`llama_get_sampled_token_ith_nosync(ctx, idx)` when
`LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`. With skip-copy enabled, the normal
`sampling.sampled` buffer is missing/null, so the fast path returns
`LLAMA_TOKEN_NULL`. The sampler then falls back to full logits, but logits are
intentionally not exported in backend-argmax mode, causing the assert.

## Strict Parity Finding

The stricter parity diagnostic compares direct egress vs copied sampled IDs for
every row, including `LLAMA_TOKEN_NULL`. It logged many mismatches like:

```text
get_sampled_tokens: direct sampled-ID egress parity mismatch at row 0: direct=-1 copied=<token>
```

That proves the direct egress pointer is not attached to the actual sampled-row
producer. The direct buffer remains unset while the existing copied sampled path
is correct.

## Decision

Reject this lane as implemented. Do not enable
`LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_SKIP_COPY`; it is invalid and crashes.
The parity flag is useful only as a diagnostic after the strict null-sensitive
comparison.

If this idea is revisited, patch the actual sampled-row producer at graph-build
time or in the direct `GGML_OP_MUL_MAT_ARGMAX` tensor, not merely the
`t_sampled_rows` output handle seen at execution. A safe implementation must
prove strict direct-vs-copied parity before any copy can be skipped.
