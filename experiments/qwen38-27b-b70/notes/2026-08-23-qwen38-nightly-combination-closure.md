# Nightly TP/MTP/graph/KV matrix: all 96 cells decision-classified

Date: 2026-08-23. Structured map:
[`2026-08-23-qwen38-nightly-combination-closure.json`](../data/2026-08-23-qwen38-nightly-combination-closure.json).

"Flush the matrix" means every Cartesian cell has a durable disposition; it
does not mean running combinations whose parent correctness or expansion gate
already failed. The bounded scope is TP 1/2/3/4 × MTP 0/1/2/3 × graph off/on ×
KV F16/e4m3/e5m2 at max model length 32K: 96 decision cells.

## F16 matrix at valid TP sizes

| MTP | graph | TP1 | TP2 | TP4 | disposition |
| ---: | --- | --- | --- | --- | --- |
| 0 | off | 23.72/24.25 | 16.77 | 17.38 | eager column measured |
| 0 | on | **30.3107 strict** | **49.0197 strict** | **71.2933/71.3984 strict** | promoted family |
| 1 | off | 4.51 | closed by parent gates | closed by parent gates | no expansion |
| 1 | on | 7.63, 0% acceptance, 0/25 oracle | quarantined | quarantined | correctness bug |
| 2 | off | 4.41 | boots/canary pass | boots; 31.17 screen misses both gates | full expansion rejected |
| 2 | on | quarantined by MTP1 anchor | quarantined | quarantined | correctness bug |
| 3 | off | 4.30 | closed after MTP2 gate | deeper ladder unauthorized | no expansion |
| 3 | on | quarantined by MTP1 anchor | quarantined | quarantined | correctness bug |

The TP4 MTP2 result is not a boot failure: isolated caches proved TP2 and TP4
boot. It is a performance/acceptance rejection. Conversely, the old shared-
cache TP4 root remains infrastructure-invalid and must not be used as the
reason for closure.

## Topology and KV closures

- TP3 covers 24 cells and is architecturally impossible: 16 GDN K heads are
  not divisible by 3.
- `fp8_e5m2` covers 24 valid-TP cells and is unsupported by the active XPU
  FlashAttention backend.
- `fp8_e4m3` covers 24 valid-TP cells. Its least-compounded TP1/MTP0/eager
  anchor is speed-neutral (`24.1009`) but matches only 3/20 stable oracle
  outputs. No TP, graph, or speculative product is promotion-eligible without
  a new quantization path that first clears that oracle.

## Result

All 96 cells are decision-classified. The only strict promoted nightly family
is F16 KV, MTP off, graph on at TP1/2/4. The eager target-only column is a
complete diagnostic control. There are no further GPU runs authorized in the
current nightly Cartesian matrix. Reopening requires an upstream graph+MTP
fix, materially changed MTP cost/acceptance, a quality-clean KV quantizer, or
new TP head-partition support.

This closure does not close the separate native-MTP dose-8 corruption program
or the v0.27.1 image-attribution cross-check.

