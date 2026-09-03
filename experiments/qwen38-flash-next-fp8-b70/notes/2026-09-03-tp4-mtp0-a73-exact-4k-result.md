# Qwen3.8 Flash-Next FP8 A73 exact-4K result

Date: 2026-09-03 08:58--09:22 EDT
Status: **complete frozen-client pass at 4352 served tokens**
(`client-gates-passed.txt` names `exact-4K-repeat`; runtime receipt passed);
first full-client record of the deterministic graph line at 4K

## Server

Byte-identical to A76/A77 apart from attempt paths: full decode graph
(`FULL_DECODE_ONLY`, size 1), public oneCCL `4ceafd1` twoshots, tuned M1
W13-N32 map, PLE-only UVA placement, `MAX_MODEL_LEN=4352`, 128 MiB cache
(4,747 KV tokens), `VLLM_XPU_MKLDNN_DETERMINISTIC=1`, overlay head
`2169dbfe...`. Launched behind a dropped page cache; weights loaded in
541.8 s from the USB copy, engine init 228.1 s, ready 14.5 minutes after
launch; client 9 minutes. No guard fired; no kernel GPU event.

## Gates

| gate | A73 (4352) | A72 (2304) |
| --- | --- | --- |
| recovery canary, identity, twoshots, W13-N32 resolver receipt | pass | pass |
| exact semantic cases | 6/7 (`code_execution=30`) | same |
| 16-repeat | 16/16 `3b0b3192...` | same |
| exact cache-zero 2K needle | pass | pass |
| short rows (after first text, tok/s) | `22.966002 / 23.898996 / 22.256402` | `24.16 / 21.88 / 23.21` |
| exact-2K rows (99-interval, tok/s; TTFT s) | `13.514374 / 14.909545` (52.2 / 47.2) | `13.18 / 14.62` |
| exact-2K output hash (both rows) | `afffd2110812...` | same |
| exact-4K rows (99-interval, tok/s; TTFT s) | **`12.728316 / 12.825225`** (98.7 / 89.5) | not served |
| exact-4K output hash (both rows) | **`c6193cc6c9a1...`** | |
| runtime receipt: size-1 FULL dispatches | 1375, 7 collective processes | 1213 |

Exact-4K median `12.776770 tok/s`; exact-2K median `14.211960`; short
median `22.966002`.

## Reading

- The exact-4K continuation `c6193cc6...` now has three servers (A76 and
  A77 by the logprob probe, A73 by the frozen depth harness with usage
  4096/128/4224, cache zero, payload `2d92a285...`), and the exact-2K
  continuation `afffd211...` has six. Both are the deterministic line's
  authorities under the decision memo's option (a); the native-line records
  (`5fd297f7...`, `1d833e5f...`) are untouched.
- Serving at 4352 instead of 2304 changed no short, quality, or 2K output.
  Speed at 4K: `12.78 tok/s` conventional against the native eager line's
  `5.27` (A9, same fixture and capacity) and the MTP3 eager screen's `4.67`
  (formal p4096/o128 row of the 2026-08-27 result). TTFT at 4K 89.5-98.7 s
  against A9's 100.8-110.1 s.
- A78, an independently started server of the same packet, is the pair
  that promotes this line at 4352 tokens.

Receipts: run dir `...attempt73/`, tracked
[`summary`](../data/20260903-tp4-mtp0-a73-exact-4k-deterministic-summary.json)
and [`runtime-after`](../data/20260903-tp4-mtp0-a73-fullgraph-runtime-after.json).
