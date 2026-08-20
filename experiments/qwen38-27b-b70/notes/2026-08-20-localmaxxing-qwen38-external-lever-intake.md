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
parity. The LocalMaxxing row does not attest exact executed bytes, but the
author linked the row to public cookbook PR #2 one minute later. The frozen
merge source is
[`patch_draft_mtp_int4.py`](https://github.com/SergiioB/intel-arc-pro-b70-inference-cookbook/blob/cd241b27509d/patches/patch_draft_mtp_int4.py),
SHA-256 `4df179c3e77fd7a248f9b9c0b60217c60caea14ebfd16b7860536fbff3b2a1e9`.

Only part of that idea is new here:

- this lane's draft LM head is already runtime INT4, so that portion is banked;
- this AutoRound checkpoint already stores most of its MTP attention/MLP block
  as INT4, while `mtp.fc` remains BF16;
- the public patch finds five fused runtime linears, but its `weight is None`
  guard skips the four already-packed AutoGPTQ modules here and would quantize
  only `mtp.fc`;
- the external checkpoint, nightly, FP8 KV, MTP4, TP1 topology, prompt, metric,
  and source patches differ from the active AutoRound FP16-KV MTP5 TP2 lane.

At TP2, `mtp.fc` is about 52.43 MB of BF16 weights per rank and about 13.52 MB
as INT4 plus scales. A bandwidth ceiling suggests roughly `0.9`–`1.0 tok/s`;
scaling the patch author's full-five-linear result suggests a more conservative
`0.5`–`0.7 tok/s`. The current vLLM source no longer matches the patch anchor,
so a narrow port and op-level timing/acceptance screen are required. Do not
infer `+32.8%` or `112.65 tok/s` transferability.

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

Do not spend a server run on any of these entries as written. The source audit
is complete: only `mtp.fc` survives as BF16 here and cannot independently bridge
the gap to 105 tok/s. A future run is justified only after the TP1 runtime
nondeterminism is localized, the narrow port wins an op-level screen, and a
target-verified acceptance/quality plan exists.
