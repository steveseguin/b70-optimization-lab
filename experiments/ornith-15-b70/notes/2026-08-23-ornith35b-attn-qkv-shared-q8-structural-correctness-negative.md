# Ornith 1.5 35B-A3B: full-attention Q/K/V shared Q8

Date: 2026-08-23 EDT

Status: **CLOSED STRUCTURAL/CORRECTNESS NEGATIVE — do not benchmark or ship**

Ornith's ten Qwen-derived full-attention layers project one contiguous FP32
activation through separate Q, V, and K weights. A candidate collected the
exact one-token `Qcur_full-*`, `Vcur-*`, and `Kcur-*` nodes, quantized their
shared 2048-element activation once, and invoked the otherwise unchanged
reordered MMVQ kernel three times. It was default-off, one-device-only, and
guarded by exact names, shapes, types, source identity, and distinct outputs.

Poison coverage aborted at the first eligible node as required. The real
triple candidate hit all 1,270 intended sites (10 layers x 127 decode
evaluations), but failed the forced-transcript gate:

| Arm | Output SHA-256 |
| --- | --- |
| accepted eleven-feature stack | `d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c` |
| shared-Q8 Q/V/K | `5a2b1fa6d2693339b2cbd0a3d28a04b56d7fb8e6b029ec08f073ac2c1ac1de57` |
| diagnostic wrapper, Q only | `aac03629ce958e8c8a214ca44f4544fc4fac058a99296b3dd740ebb3a267ca44` |

The Q-only isolation identifies the premise error. At one-token decode on
B70, these projections take the reordered ESIMD DMMV branch, which consumes
FP32 directly. They do not launch Q8 activation quantization. The candidate
changed the projection algorithm to Q8-MMVQ even before any input reuse, so
the transcript change is expected and there are no redundant Q8 launches to
remove from this path.

No throughput measurement was run. The rejected incremental source is
preserved at
`../patches/llamacpp-ornith15-attn-qkv-shared-q8-structural-correctness-negative-20260823.patch`;
raw poison and transcript records are under `../data/2026-08-23-ornith35b-attn-qkv-shared-q8-*`.

