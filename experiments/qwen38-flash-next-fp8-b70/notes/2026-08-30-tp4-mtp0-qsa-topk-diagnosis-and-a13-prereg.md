# Qwen3.8 Flash-Next FP8 QSA diagnosis and A13 preregistration

Date: 2026-08-30
Status: mechanism reproduced; deterministic treatment frozen before full-model run

## Why the 4K-only boundary now has a concrete mechanism

The checkpoint's QSA indexer retains 2,048 tokens at a compression ratio of
four, or 512 compressed groups. At short depths up through roughly 2K, every
visible complete group is retained. At exact 4K, QSA must choose 512 of roughly
1,024 visible groups. This explains why the 16-row short repeat can remain
token-stable while exact-4K repeats vary.

The XPU top-k source emits strict winners through local atomic reservations and
uses reservation position to resolve cutoff ties. QSA then consumes that order
directly. A bounded B70 microtest used 400 strict winners and 624 exact cutoff
ties, selecting 512 entries over 100 identical launches. The existing operation
returned 32 distinct hashes. Stable argsort and ordinary sorted top-k each
returned one. The isolated mean timings were `20.04 us` for the existing
operation, `24.78 us` for stable argsort, and `28.56 us` for sorted top-k.

This is direct reproduction of a repeatability mechanism, not yet proof that it
is the only full-model mechanism. It is consistent with A12: score vectors vary
before greedy selection once QSA subset selection becomes active.

## Treatment

vLLM commit `f68c9386fe5af54055bdf20684b269b9c1340e44` changes only XPU QSA
selection. It uses stable descending argsort, whose stable secondary order is
logical index ascending, and masks ranks beyond each row's visible count. It
does not perturb scores, weights, quantization, PLE placement, attention budget,
or CUDA/ROCm dispatch. The focused Qwen4Exp XPU suite passes 5/5, including 32
repeated exact-tie selections. Ruff check and format also pass.

The patch is preserved at
[`../../../patches/qwen38-flash-next-fp8-b70/vllm/0019-Make-Qwen4Exp-XPU-QSA-selection-deterministic.patch`](../../../patches/qwen38-flash-next-fp8-b70/vllm/0019-Make-Qwen4Exp-XPU-QSA-selection-deterministic.patch)
with SHA-256
`df44c39f0c25cb6b05365d5de31afa9e0d3b251b070b371ae71d96080979afcd`.
It is a candidate, not part of the promoted production series yet.

## Frozen A13 arm

A13 starts a new TP4/EP4/eager/MTP0 server and changes only the vLLM head from
`e5137bfd8` to `f68c9386f`. It retains:

- model revision `bcd9f01d...ddce` on local NVMe;
- the 51.200-GB PLE table as the sole UVA/host-resident parameter;
- input embedding in VRAM, 128-MiB cache, 4,352-token capacity, and one sequence;
- the staged native runtime at build head `2f829747`;
- graph off, prefix caching off, async scheduling off, MTP0, fixed seeds, and
  every quality/request identity from A10.

The unchanged battery is recovery canary, established seven-case semantic gate,
16 identical short repeats, exact-4K needle, three ordinary p146/o256 rows, and
two byte-identical p4096/o128 rows. All short hashes must equal
`5f407446...f89f0`; both exact-4K hashes must equal retained authority
`1d833e5f...39d5cc`. Cached tokens must remain zero. Any mismatch fails closed
and receives no performance or promotion credit.

If A13 passes, its ordinary no-logprob timing is additive evidence and a fresh
server A14 repeat is required before calling the treatment reliable/lossless.
If it fails, preserve it and do not change protected speeds. No deeper context,
MTP, graph, prefill, or MoE tuning is authorized inside A13.

Frozen artifacts:

- launcher wrapper `2b9557fd...2f7ad`, generated source
  `0c973721...b2443`;
- client wrapper `0240ce9f...ab0c7`, generated source
  `a7be5d90...bb05c`;
- supervisor wrapper `d5ce14b5...c2454`, generated source
  `21d301cb...2c75f`.

Structured diagnosis:
[`../data/20260830-xpu-qsa-topk-repeatability-diagnosis.json`](../data/20260830-xpu-qsa-topk-repeatability-diagnosis.json).
