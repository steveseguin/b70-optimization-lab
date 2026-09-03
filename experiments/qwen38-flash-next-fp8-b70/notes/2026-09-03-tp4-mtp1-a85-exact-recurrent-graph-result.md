# Qwen3.8 Flash-Next FP8 A85 result: the serial-exact recurrent path inside the graph

Date: 2026-09-03 11:52--12:15 EDT
Status: **diagnostic; the exact recurrent spec-decode path works in the full
decode graph and removes part of the MTP1 gap, not all of it**

## Server

The A81 packet with `MTP_EXACT=1`: sealed exact stage
`runtime-mtp1-exact-ad25aa9-b70` (stage build head `ad25aa9`, source head
`e421889`), `VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1` with
persistent scratch, MTP1, `cudagraph_capture_sizes` [1, 2], 32-block KV,
NVMe copy. All four ranks logged the exact-mode marker, graph capture took
56 s, the base's exact-mode canary passed, ready 8 minutes after launch.
First end-to-end measurement of this mode (the 2026-08-27 attempt never
spawned a worker).

## Battery against the MTP0 line's pins

| gate | A85 (MTP1 exact-recurrent, graph) | A81 (MTP1, graph) | MTP0 line |
| --- | --- | --- | --- |
| short rows (tok/s) | `31.221493 / 32.274535 / 36.770651`, median `32.27` | `38.79 / 44.02 / 38.53` | `22.26-24.73` |
| short hash | `5f407446...` | same | same |
| quality 7 cases / 16-repeat / needle | 6/7 identical outputs, `3b0b3192...`, pass | same | same |
| exact-2K rows (tok/s; TTFT s) | `7.498507 / 8.923615` (124.4 / 100.2) | `7.25 / 6.91` | `13.44-14.91` |
| exact-2K hash; first divergence from the MTP0 line | `29a2947a...` at **token 12** | `460b0d5c...` at token 7 | `afffd211...` |
| exact-4K hash | `bf25b9d1...` (equals A81) | `bf25b9d1...` | `c6193cc6...` |
| draft acceptance | 734 of 790 | 733 of 787 | |

Token 12 of the 2K fixture is the near-tie where the native line's own two
authorities (`5fd297f7...` / `afffd211...`) split; the exact recurrent path
now agrees with the MTP0 line through token 11 and flips there.

## Companion gate

`tools/equivalence-m2-vs-m1-gemm-gate.py` (card 0, mkldnn deterministic):
a two-row BF16 GEMM is bit-identical to two one-row GEMMs at every decode
shape tried, including the K=10240 hyperconnection mix, N=640 MoE slice,
5120x2048 and 2048x8192; all shapes self-repeatable. The oneDNN dense
projections are M-invariant. Data:
[`gemm gate`](../data/20260903-b70-bf16-gemm-m2-vs-m1-equivalence.json).

## Reading

- The exact recurrent path is functional under graph capture and costs
  about 15% of the plain MTP1 short rate (32.3 against 38.8 tok/s, still
  1.42x the MTP0 line). It removes the GDN recurrent contribution to the
  gap; what remains flips the 2K near-tie at token 12 and leaves the 4K
  continuation unchanged.
- The dense GEMMs are cleared by the companion gate. The remaining
  two-row-versus-one-row candidates are the Triton block-FP8 MoE (the tuned
  map has no key 2; M=2 resolves to the key-4 config with `num_warps` 4
  and no W13-N32 override, a different tiling from key 1) and the two-row
  path of the full-attention layers (the 27B lane needed serial spec
  attention, R38, for exactly this). A86 tests the MoE candidate cheaply
  with a map whose key 2 equals key 1; attention comes after.

Data: [`diagnostic`](../data/20260903-tp4-mtp1-a85-exact-recurrent-graph-diagnostic.json).
