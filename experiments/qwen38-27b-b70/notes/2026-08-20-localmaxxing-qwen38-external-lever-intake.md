# LocalMaxxing Qwen3.8 external-lever intake

Date: 2026-08-20

Status: read-only public-feed review; no external row is a lab result

The public API was checked for newer Qwen3.8/B70 and DFlash2 entries. Results
were classified by benchmark identity and reproducibility, not ranked by the
largest displayed number.

## Potentially relevant single-stream mechanism

LocalMaxxing
[`cmszpqy000e8fms014ty6i5x3`](https://www.localmaxxing.com/en/runs/cmszpqy000e8fms014ty6i5x3)
reports `112.65 tok/s` at p512/g128 on one B70 with SergiioB's GPTQ-INT4
checkpoint and an XPU nightly. Its claimed change is runtime INT4 for both the
draft LM head and five MTP linears, versus a matched BF16-draft `81.20` arm.
The entry explicitly says it is speed-only with no token, KL, or task-quality
parity, and its patch scripts are not in this repository or discoverable in the
linked public cookbook.

Only part of that idea is new here:

- this lane's draft LM head is already runtime INT4, so that portion is banked;
- this AutoRound checkpoint already stores most of its MTP attention/MLP block
  as INT4, while `mtp.fc` remains BF16;
- the external checkpoint, nightly, FP8 KV, MTP4, TP1 topology, prompt, metric,
  and source patches differ from the active AutoRound FP16-KV MTP5 TP2 lane.

The remaining useful question is narrow: obtain/read the exact
`patch_draft_mtp_int4.py`, map its five linears against this checkpoint's
already-quantized tensors, and op-screen only genuinely BF16 survivors such as
`mtp.fc`. Do not infer `+32.8%` or `112.65 tok/s` transferability.

## Numbers that are not single-stream optimization leads

Several `107.8`–`224.2 tok/s` one-B70 rows use the same SergiioB checkpoint but
report aggregate C5/C32 serving throughput and expose only a remote-endpoint
placeholder instead of a reproducible command. They are concurrency/capacity
identities, not comparisons to this lane's single-request cold median.

The `136.4 tok/s` TP2 row
[`cmt0vu76q0fvtms017exhssx9`](https://www.localmaxxing.com/en/runs/cmt0vu76q0fvtms017exhssx9)
uses an uncensored checkpoint, a GPTQ config flip, host-staged collectives,
MTP3, and a newer patched runtime. Its own notes give `94.58 tok/s` for the
strict cold suite. It therefore supplies possible source-reading leads, not a
faster like-for-like result.

The newest 100 rows contained six DFlash2 commands on R9700/RTX 5090 or
unidentified hardware, spanning about `27`–`282 tok/s`, and no B65/B70 DFlash2
row. See the separate
[DFlash2 intake](2026-08-20-dflash2-future-lane-intake.md) for its evidence
boundary.

## Queue implication

Do not spend a server run on any of these entries as written. After the fresh
oracle and TP1 determinism diagnostic, the best low-cost follow-up is a source
audit of the five-linear draft quantization patch. A run becomes justified only
if the exact delta is available, a currently-BF16 tensor is proven hot, and a
target-verified acceptance/quality plan exists.
