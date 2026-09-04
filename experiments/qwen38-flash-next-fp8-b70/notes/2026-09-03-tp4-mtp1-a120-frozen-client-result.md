# A120: the frozen MTP1 client passes end to end (2026-09-03, 22:08-22:30)

First complete pass of a frozen MTP1 client on the deterministic
full-decode-graph line. Identity: overlay `1b2a17c1`, kernels `e421889`,
stage build `2f829747`, TP4/EP4, `FULL_DECODE_ONLY` with capture sizes
[1, 2], MTP1 (`num_speculative_tokens` 1, `mtp_exact_recurrent=0`), KV
376569856 bytes, 4352 served tokens, PLE-only UVA, W13-N32 MoE map, public
oneCCL twoshots, `VLLM_XPU_MKLDNN_DETERMINISTIC=1`, and the three
exact-verify selectors (`VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`,
`VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2`, `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2`),
each checked in the live server environment by the client. Runtime
verifier `verify-q38-a114-fullgraph-runtime.py` chain via
`verify-q38-a118-fullgraph-runtime.py` (A48 twoshots chain, capture [1, 2],
size-2 FULL dispatch receipt). Client gates: `PASS recovery quality
short-repeat exact-2K-repeat exact-4K-repeat PLE-only 4352 MTP1 QSA-stable
treatment`. A first launch of this packet lost its API server to a segfault
before the client ran (22:07); the relaunch is this run.

| gate | A120 | MTP0 line (A73/A78) |
|---|---|---|
| recovery canary | passed | passed |
| quality | 6/7 semantic (`code_execution=30`), 16/16 one hash `3b0b3192...`, exact needle, cache zero | same |
| short p146/o256 after first text, tok/s | `22.19 / 28.39 / 26.72`, median `26.72`, hash `5f407446...` | center `22.66`, same hash |
| exact 2K p2048/o128, 99-interval tok/s (TTFT s) | `8.92 / 8.84` (94.7 / 83.5), hash `afffd211...` | median `13.99` (56-58), same hash |
| exact 4K p4096/o128, 99-interval tok/s (TTFT s) | `7.14 / 7.43` (149.7 / 145.2), hash `c6193cc6...` | median `12.78` (96-103), same hash |
| runtime receipt (after) | 786 size-2 FULL dispatches, 0 size-1, 7 collective processes, twoshots | 1375 size-1 |

Every output equals the MTP0 line's authority: the MTP1 line changes no
answer. Speed: the client's short rows (which follow the quality suite) run
`26.7` median against the MTP0 center `22.66` (1.18x; the cold-first
diagnostic battery A113 gave `31.3` median, 1.38x); depth rows are
`0.6x` with about 1.6x the time to first token. A121 is the byte-identical
fresh-server repeat. Data:
`../data/20260903-tp4-mtp1-a120-frozen-client-summary.json`,
`../data/20260903-tp4-mtp1-a120-fullgraphdet-runtime-after.json`.
Packet: `tools/{launch,supervise}-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32.sh`,
`tools/run-tp4-mtp1-4352-ple-only-a120-fullgraphdet-w13n32-client.sh`,
`tools/run-q38-a120-host-controlled.sh` (generator
`tools/rewrite-q38-a113-to-a120-mtp1-client.py`).
