# Batched DFlash backend argmax: retained win

Date: 2026-08-13

## Decision

Retain the default-off batched backend-greedy graph.  It changes the DFlash
draft block from 16 independent one-row distributed argmax/maxloc boundaries
to one 16-row argmax and one TP maxloc.  The final C/A/C improves the already
retained device-greedy stack from pooled `71.372 tok/s` to **`72.990 tok/s`**
(**+2.267%**) with canonical hashes and identical accepted-token counts.
No drafter training was performed.

## Final result

All arms used BF16 Muse, BF16 DFlash, TP4, `n_max=15`, `p_min=0`, greedy,
cache off, parallel one, and the fixed three 256-token prompts.

| arm | prose | code | JSON | mean |
| --- | ---: | ---: | ---: | ---: |
| unbatched control before | `50.996` | `73.821` | `89.307` | `71.375` |
| batched candidate | **`52.143`** | **`75.500`** | **`91.327`** | **`72.990`** |
| unbatched control after | `50.845` | `73.760` | `89.502` | `71.369` |

Candidate output hashes are canonical: prose `914f754747d0edaa`, code
`cf2b2c4fd9e36fe5`, JSON `4f813a9706abc163`.  Candidate acceptance is exactly
`172/197/207`, matching both controls.  The live diagnostic proves the intended
collective shape:

```text
[comm-dbg] batched argmax fast path: n_backends=4 n_rows=16
```

## Design

The sampler graph detects a backend-initialized chain containing only terminal
greedy.  When its output rows are consecutive, it passes a two-dimensional
logits view to `ggml_argmax`; ggml already reduces axis zero independently for
each row.  The existing meta/SYCL communicator therefore receives one I32
vector and executes its existing row-capable maxloc once.  Per-row result views
are added to the graph explicitly for the existing asynchronous host extraction
API.  The path is gated by `LLAMA_BACKEND_GREEDY_BATCH_ROWS=1`; all existing
fallback behavior remains unchanged.

Source commit: `/home/steve/src/llama.cpp-muse-100` `5302413a3`
(`sampling: batch backend greedy output rows`).  The other retained gates are
`LLAMA_DFLASH_TP_GREEDY=1`, `LLAMA_TP_BACKEND_SAMPLING=1`, and
`GGML_SYCL_COMM_ARGMAX=1`.

## Failed first proof

The first batched smoke created per-row views after selecting the batched
tensor but did not add those views to the compute graph.  Host extraction then
asserted because the scheduler had assigned no backend to the views.  No output
row was emitted.  Explicitly expanding the views into the graph fixed the
lifetime/backend assignment; the corrected short smoke matched all three
unbatched hashes before admission to the full C/A/C.

## Timeline diagnostic

A sparse profiling-tag run on the prior `71.859 tok/s` stack confirmed that the
DFlash context contained repeated ARGMAX work and motivated this patch.  Its
absolute throughput (`13.5/16.4/25.0 tok/s`) and tag-bracket timings are not
benchmark evidence: sampling one in eight logical operations still heavily
perturbs the in-order queues.  The useful evidence was graph/collective
structure, later confirmed directly by the live `n_rows=16` marker.

## Evidence

- final JSONL:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-batched-argmax-final-ab-20260813.jsonl`,
  SHA256 `18be7bb9ede99471a6e971fe6a9373737f4cfc6e12a562e5333d307b5e076d51`;
- final identity:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-batched-argmax-final-ab.json`;
- corrected smoke:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-batched-argmax-fix-smoke.json`;
- failed first proof:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-batched-argmax-smoke.json`;
- timeline identity:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-device-timeline-best-stack.json`;
- timeline result SHA256
  `af6370b1e62716bf0af5ebaf32f84568d2e1c9e019d087630af0f9b0754220fa`;
- timeline log SHA256
  `1482ecf67487f680e8e01942ee8316545e517ecd4af8358c7bb6fe99871206be`;
- restored production health:
  `data/muse-health-20260813-dflash-batched-argmax-final-restore.json`.

The source rebuilt through `llama-server`; `git diff --check` passed before the
focused commit.  Production was restored without reboot, both services are
active, and the full model/cache-zero code/vision health gate passes.  The TP2
production fleet was not changed.
