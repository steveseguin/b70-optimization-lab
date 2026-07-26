# Laguna width-12 DFlash FP8 W8A16 record

Date: 2026-07-26 America/Toronto

Status: **verified exact four-B70 result; LocalMaxxing APPROVED; throughput
metric qualified by a later accounting audit**

> Correction: `102.97143559613157 tok/s` is the submitted historical
> `100 events / 99-interval span` convention. The conventional interval rate
> from the same sealed timestamps is `101.94172124017027 tok/s`. See the
> [accounting correction](2026-07-26-throughput-window-accounting-correction.md).

## Result

The preregistered single cold candidate measured:

```text
102.97143559613157 tok/s
```

This is the submitted legacy-convention median over the fixed 13-prompt
realistic suite. It exceeds 102 under that convention by
`0.97143559613157 tok/s`. The conventional 99-interval median is
`101.94172124017027 tok/s`, short of 102 by `0.05827875982973 tok/s`.

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-width12-dflash-fp8-e596ef154-20260726T214259Z
```

No warmup request or generation was run. Every prompt was invoked once, there
was no retry, and this first valid score is the reported score.

## Required gates

| gate | result |
|---|---:|
| canonical q=1 teacher exactness | `13/13`, token IDs and text bitwise exact |
| cached prompt tokens | `0/13` nonzero; all 13 are zero |
| realistic final gate | pass |
| one active generation | pass |
| target graph captures | 4 ranks, each exactly `146/145` |
| target graph replays | 4 ranks, each exactly `146/145` |
| prestart verified idle interval | 73 seconds, 13 snapshots |
| poststop verified idle interval | 73 seconds, 13 snapshots |
| shutdown / worker / idle cleanup statuses | `0 / 0 / 0` |
| surviving vLLM workers or port-18080 listener | none |

The long rollover prompt and the long-then-next boundary are exact. The
benchmark reports `fresh-response`, no context checkpoint, no prefix/history
acceleration, no response reuse, and no cached tokens.

## Identity

- target: `poolside/Laguna-S-2.1-INT4`, revision
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft: `poolside/Laguna-S-2.1-DFlash-INT4`, revision
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- vLLM source: `e596ef1543466ae1a05e5bb8091f58872e2b18ba`;
- XPU-kernel source: `6f9dd3c3a7b1b677a992ca4f431a968408f9c816`;
- target execution: TP4+EP4, one sequence, BF16 KV, exact width 12,
  DFlash depth 11, greedy drafts, standard rejection sampling;
- graph: compile mode NONE, PIECEWISE Breakable capture size 12,
  persistent exact-attention metadata, `146/145` audited topology;
- width-12 exact stack: batched exact MoE, BF16 router top-k, and persistent
  DFlash context-KV workspace;
- new selector: `VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=1`;
- prefix caching, local draft argmax, draft graph capture, target attention
  subgraph capture, and inline attention are all off.

The service environment and `identity.txt` independently record the selector
and worktree identities.

The local source commits are preserved as exact Git bundles and reviewable
combined patches under `patches/laguna-s-2.1-xpu-b70/`. See that directory's
README for public prerequisite commits, restore commands, and snapshot
checksums.

## Throughput and speculation

| metric | value |
|---|---:|
| submitted legacy median, 100 events / 99-interval span | `102.97143559613157 tok/s` |
| conventional median, 99 intervals / same span | `101.94172124017027 tok/s` |
| submitted legacy p10 | `71.14888383025148 tok/s` |
| submitted legacy mean | `119.43840854755922 tok/s` |
| full-output after-TTFT median | `134.79088555311446 tok/s` |
| full wall-throughput median | `52.76762062661338 tok/s` |
| median TTFT | `5758.738295000512 ms` |
| draft cycles | `1609` |
| draft tokens | `17699` |
| accepted draft tokens | `4747` |
| accepted draft-token rate | `26.820724334708174%` |
| emitted tokens per draft cycle | `3.950279676817899` |

The suite-level speculative counts are essentially matched to the preceding
exact width-12 router/workspace candidate (`1608` drafts and `4748` accepted
tokens). The new result therefore does not obtain its gain by inflating
acceptance.

Relative to the approved `94.92003934159611 tok/s` four-B70 record, this is
`+8.051396254535462 tok/s` or `+8.48229342337321%`. Relative to the previous
best exact but unsubmitted width-12 leg at `100.5248896052723 tok/s`, it is
`+2.4465459908592635 tok/s` or `+2.433771377880678%`.

## What the artifact proves about the treatment

Every rank logged conversion of exactly 31 DFlash dense projections to the
default-off per-output-channel E4M3FN W8A16 method. The selector also chooses
the stable auxiliary hidden-slice workspace path. The target model, target
LM head, target logits, verifier, rejection sampler, target KV state, and
sampling policy remain unchanged; the 13/13 teacher comparison is the final
semantic gate.

The source contains an intended separate FP8 draft-LM-head preparation path,
but the server log does **not** contain its expected preparation message.
Consequently, this record does not attribute any measured gain to the draft
LM head. The evidence-backed treatment description is the 31 converted draft
projections plus the auxiliary workspace on the already-validated width-12
router/context-KV stack. A future experiment must add an explicit runtime
postcondition before claiming or measuring the separate FP8 head.

## Checksums

| artifact | SHA256 |
|---|---|
| `bench.json` | `a266b6ed28fa963456b3fc626a8bbafe104433e8b5dbc0b749973f6cd5e7f413` |
| `exactness-vs-q1.json` | `f69e461b88ce6291af7a31716e2a0184a3918ed0a9b517768b30425107b0e275` |
| `server.log` | `5e082ef3cf85734119baa9f05ec83bcbca993408e5b0ad61c65169abfaa9a177` |
| `identity.txt` | `3569a13ae94a55d020d4250c23d1a67fb5e6310303e179a09e1e92f4b6c2ca8b` |
| `metrics-after-suite.prom` | `d74847ab08a05b512bbf22b8b8cbc11c52fb480455c7cf74cc1eca33144237af` |

The run directory was sealed read-only by the harness after successful
teardown.

## LocalMaxxing

The current speed-test API accepted the record on 2026-07-26:

- ID: `cms2ccv2d00lps201rej94pjy`;
- status: `APPROVED`;
- HTTP receipt: `201 Created`;
- queue:
  `data/localmaxxing-laguna-s-2.1-int4-b70-width12-dflash-fp8-102.971tok-20260726.queue.json`;
- response:
  `data/localmaxxing-responses/laguna-s-2.1-int4-b70-width12-dflash-fp8-102.971tok-20260726.response.json`.

The public row was queried back and matched the score, model revision, four
B70s, vLLM engine, TP4, DFlash model, and depth 11. LocalMaxxing reused an
older canonical hardware object that displays `cpu=null` and `ramGb=15`;
those two public display fields are not the actual host identity. The tracked
queue and sealed run identify the actual Threadripper PRO 5955WX host with
128 GB RAM.
