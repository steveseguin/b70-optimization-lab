# Qwen3.8 Flash-Next FP8 A78 fresh-server repeat result

Date: 2026-09-03 09:27--09:51 EDT
Status: **complete frozen-client pass; every output identical to A73**. The
4352-token deterministic full-decode-graph line has its two-server record.

## Server

The A73 packet renamed to attempt 78 / port 19750; launched behind a
dropped page cache after the swap-usage guard refused a first launch (38 MB
of swap in use after the NVMe-copy hashing; cleared by swapoff/swapon, the
wrapper's own toggle). Weights 545.9 s from USB; ready 14.5 minutes after
launch; client 9.5 minutes. No guard fired; no kernel GPU event.

## Gates (A78 against A73)

| gate | A78 | A73 |
| --- | --- | --- |
| recovery canary, identity, twoshots, W13-N32 receipt | pass | pass |
| exact semantic cases (all 7 normalized outputs) | 6/7, identical text | same |
| 16-repeat | 16/16 `3b0b3192...` | same |
| exact cache-zero 2K needle | pass | pass |
| short rows (after first text, tok/s) | `22.355390 / 23.350884 / 22.321053` | `22.966002 / 23.898996 / 22.256402` |
| short output hash | `5f407446...` | same |
| exact-2K rows (99-interval tok/s; TTFT s) | `13.443310 / 14.471953` (58.3 / 56.1) | `13.514374 / 14.909545` (52.2 / 47.2) |
| exact-2K output hash | `afffd2110812...` | same |
| exact-4K rows (99-interval tok/s; TTFT s) | `13.498466 / 12.241721` (102.5 / 96.4) | `12.728316 / 12.825225` (98.7 / 89.5) |
| exact-4K output hash | `c6193cc6c9a1...` | same |
| runtime receipt: size-1 FULL dispatches | 1412 | 1375 |

The summaries differ only in timings (checked field by field).

## Record of the 4352-token deterministic line (A73 + A78)

- short after-first-text: medians `22.966002` (A73) and `22.355390` (A78);
  two-attempt center **`22.660696 tok/s`**; six rows `22.26-23.90`;
- exact 2K (p2048/o128, conventional 99-interval): four rows
  `13.44-14.91`, median **`13.993164 tok/s`**, TTFT 47-58 s;
- exact 4K (p4096/o128): four rows `12.24-13.50`, median
  **`12.776770 tok/s`**, TTFT 89-103 s;
- outputs: one hash per gate across both servers, and the same hashes as
  the 2304-token servers A70-A72 where the gates overlap; exact-4K hash on
  four servers (A76, A77 probes; A73, A78 harness), exact-2K on seven.

Against the native (logit-jittery) line's protected rows: MTP0 eager exact
4K `5.27` (A9) and `4.76` (current-runtime anchor), MTP3 eager exact-4K
formal `4.67`; the deterministic line is 2.4-2.7x faster at 4K with no
speculation, and it is the only Flash-Next line whose outputs a third party
can reproduce on demand.

Receipts: run dir `...attempt78/`, tracked
[`summary`](../data/20260903-tp4-mtp0-a78-fresh-repeat-deterministic-summary.json)
and [`runtime-after`](../data/20260903-tp4-mtp0-a78-fullgraph-runtime-after.json).
