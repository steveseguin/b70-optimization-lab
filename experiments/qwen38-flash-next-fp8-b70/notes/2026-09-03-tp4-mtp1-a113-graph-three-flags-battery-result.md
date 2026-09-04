# A113: the full-decode-graph MTP1 line is lossless (2026-09-03, 20:33-20:56)

Identity: the deterministic 4352-token full-decode-graph line (A73/A78
identity: `VLLM_XPU_MKLDNN_DETERMINISTIC=1`, W13-N32 MoE map, PLE-only UVA,
public oneCCL twoshots, NVMe model copy) with MTP1 (`num_speculative_tokens`
1, KV 376569856 bytes, capture sizes [1, 2]) and the three exact-verify
selectors `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`,
`VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2`, `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2`
on overlay 1b2a17c1. Diagnostic battery (three short rows, two exact-2K,
two exact-4K, the quality suite, metrics), first launch after the 20:29
reboot; the first A113 launch (18:10) ended in a silent host freeze at
worker initialization.

| gate | A113 (graph MTP1, three flags) | MTP0 line (A73/A78) |
|---|---|---|
| short p146/o256, tok/s after first text | `31.20 / 34.73 / 31.31`, median `31.31` | center `22.66` |
| short output hash | `5f407446...` (= MTP0) | `5f407446...` |
| exact 2K p2048/o128, 99-interval tok/s (TTFT s) | `8.55 / 8.47` (151.2 / 100.5) | median `13.99` (56-58) |
| exact 2K hash | `afffd211...` (= MTP0 authority) | `afffd211...` |
| exact 4K p4096/o128, 99-interval tok/s (TTFT s) | `7.69 / 7.27` (193.9 / 163.1) | median `12.78` (96-103) |
| exact 4K hash | `c6193cc6...` (= MTP0 authority) | `c6193cc6...` |
| quality | 6/7 semantic (`code_execution=30`, the inherited miss), 16/16 one hash `3b0b3192...`, exact needle | same |
| draft acceptance over the battery | 735 of 785 (93.6%) | |

Every output pin equals the MTP0 line's: MTP1 on this line changes no
answer. It is 1.38x faster at short context and slower at depth (0.61x at
2K, 0.57x at 4K, with roughly double the time to first token), the same
depth cost A81 showed before the exactness work (A81: 7.25/6.91 at 2K), so
the three selectors cost nothing measurable there; the depth cost is the
MTP1 step itself (the drafter runs eagerly on XPU because only piecewise
graphs support it, and the per-step cost grows with context). A114 (the
frozen MTP1 client on this identity) and A115 (its fresh-server repeat)
are the promotion pair; the depth cost is the next lever.

Data: `../data/20260903-tp4-mtp1-a113-graph-three-flags-battery.json`.
Run: `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-4352-ple-only-r1-attempt113`.
