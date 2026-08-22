# Qwen3.8 Q4_K_M TP1: in-kernel Q8 emission rejected (fp-model=fast cross-TU)

Date: 2026-08-21

Status: **bounded negative; door preserved default-off; memo hardening kept.**

## What was attempted

Extend the fused Q4_K gate/up/SwiGLU kernel to emit its output's
reordered-SOA Q8_1 into the dedup cache, eliminating the 64 largest
per-graph activation-quantize launches (the ffn_out consumers). The emit
variant uses one aligned 32-row workgroup per Q8_1 block, replicates
`quantize_and_reorder_q8_1_soa<2>`'s lane mapping, reduction order, and
d/sum stores at source level, and leaves the incumbent kernel untouched
(door `GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K_Q8OUT`, default off, with POISON and
VERIFY sub-doors). Mechanism proved: 64 emissions per decode graph and
exactly 64 fewer quantize launches; the dst-only control proved the
variant's f32 outputs bit-identical to the oracle.

## Why it is rejected

The route output diverged from the TP1 oracle deterministically (single
token flip ~1,400 chars into the fixed probe). Byte-level verification
against the real quantizer, once the report cap was removed, localized it:
**exactly one quant byte differs on roughly half the emissions, scattered
positions, quants region only, d and sum always identical** — a ±1
`round(v/d)` round-half flip. Root cause: icpx compiles SYCL device code at
`fp-model=fast` per translation unit, so the division/rounding sequence
lowers differently in `mmvq.cpp` than in the quantizer's `ggml-sycl.cpp`
instantiation. Source-level replication therefore cannot guarantee byte
equality across TUs on this stack, and the only guaranteed-equal variant —
launching the actual quantizer kernel — saves no launches. A same-binary
bisect ladder proved every other suspect innocent: reservation/hit
mechanism (standalone-fill == oracle), memo-ring eviction (320-slot build
unchanged), and races (deterministic across fresh servers, unchanged under
verify serialization).

Estimated foregone gain was only ~0.3-0.5%; enabling the door would demand
a full oracle reset plus quality battery. Not worth it. Do not enable.

## What the investigation hardened

1. **Latent producer-eviction landmine, now documented at the constant:**
   fused Q8 producers (e.g. the engaged ATTN producer) skip computing their
   f32 output entirely, so a q8-memo entry evicted between producer and
   consumer would make the consumer requantize an unwritten buffer. With
   the historical 16 slots this never fired only because producer-consumer
   ring distances stayed small. `GGML_SYCL_Q8_MEMO_SLOTS` is now 320
   (covers a full 64-layer decode graph; a few KB per slot), verified
   inert: door-off probe text equals the oracle and quantize launches are
   unchanged.
2. The `Q8OUT_VERIFY` door remains as a reusable device-side byte
   comparator for any future producer work.
3. Transferable rule: on this toolchain, byte-exact replication of any
   quantization/kernel math **must reuse the same compiled code**, not
   re-derive it from the same source; fp-model=fast makes per-TU codegen
   part of the route identity.

- Artifact: `patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-q8out-rejected-memo320-20260821.diff.gz.b64`
  (decoded SHA-256
  `717bc1cc3eda198ded7df4e2a0046fd1ce88434c47e702feecaf4dff258142d0`).
- Final default-build sanity: probe text equals the oracle at 28.0 tok/s.
