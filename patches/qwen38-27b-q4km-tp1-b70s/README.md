# Qwen3.8 27B Q4_K_M TP1 lane patches (four-B70 measuring host)

This directory preserves incremental source deltas for the target-only TP1
lane registered in
[`experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q4km-tp1-lane-open.md`](../../experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q4km-tp1-lane-open.md).
The lane base is the exact promoted TP2 stack: mndodd
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` plus the full lab TP2 patch
(`f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998`) plus the
Q4_K GLU increment
(`0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6`), restored
per [`../qwen36-27b-q8-tp2-asrock-b70/README.md`](../qwen36-27b-q8-tp2-asrock-b70/README.md)
and [`../qwen38-27b-q4km-tp2-asrock-b70/README.md`](../qwen38-27b-q4km-tp2-asrock-b70/README.md).

## 2026-08-21: GDN state-I/O matcher widened to full-model shapes

- Artifact: `llama-cpp-tp1-gdn-state-io-widen-20260821.diff.gz.b64`
- Decoded patch SHA-256:
  `1377fd89ea595f4d6e0654ce07387f9e0c2438f6677360c4c94cd99072ce6272`
- Scope: 1 file (`ggml/src/ggml-sycl/ggml-sycl.cpp`), matcher-only; no kernel
  change. The in-place GDN kernel already derives `H` and `S_v` from tensor
  dimensions at runtime.

The accepted `GGML_SYCL_FUSED_GDN_STATE_IO` fusion admitted only the TP2
per-device half-shape (`128 x 128 x 24`, `value->ne[1] == 24`), so at TP1 the
full-model 48-head shape fell back to the stock
`GET_ROWS -> GATED_DELTA_NET -> CPY` round trip on all 48 GDN layers. This
increment admits `ne[1]` in `{24, 48}` and requires the state element count to
equal `128 * 128 * ne[1]`, preserving every other strictness condition (single
row, contiguity, unique consumers, non-overlapping persistent state, poison
door reachability).

Validation on the TP1 lane (GPU 0, fresh server per leg, fixed cold
12-prompt realistic suite, `cached_tokens=0` on all requests):

- baseline A/B: `26.047863` / `26.068073 tok/s` conventional median;
- candidate C/D: `27.358865` / `27.351846 tok/s` (**+5.033% / +5.006%**);
- output exactness: 24/24 complete output SHA-256 hashes identical to the
  registered TP1 baseline oracle across both candidate legs;
- mechanism: `fused_gdn_state_ios=282720` per leg (48 per decode graph);
- build: oneAPI 2026.0.0 BMG-G31 AOT; candidate `llama-server` SHA-256
  `55707905e7e57b7a8c4932714ba459cdbb0e11bf39b4dd3258a6c0ba0d31a477`.

Result note:
[`2026-08-21-qwen38-q4km-tp1-gdn-state-io-result.md`](../../experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q4km-tp1-gdn-state-io-result.md).
