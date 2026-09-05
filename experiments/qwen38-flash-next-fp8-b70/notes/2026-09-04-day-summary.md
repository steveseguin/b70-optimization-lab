# Day summary, 2026-09-04 (four-B70 host, Flash-Next FP8 TP4 lane)

Goals: `plans/2026-09-04-goals.md`. Host was reset at 09:42 before the
session (post-reboot routine: results drive remount, `xe` reload so the
B70s keep minors 0/2/3/4, tuning), no GPU faults since.

## Morning

- **Published the deterministic lines.** `families/qwen-flash-next.json`
  gained a `FULL_DECODE_ONLY` graph-mode axis value and six lab-measured
  entries (MTP0 A73/A78 short, exact-2K, exact-4K; lossless MTP1 A120/A121
  short, exact-2K, exact-4K); the exact-4K MTP0 row is the family hero;
  `tools/build-family-pages.py` regenerated `models/qwen-flash-next.html`
  and `models/index.html` with the coverage check clean (the check had been
  failing on an unmapped rapid-snapshot README, now mapped in the
  registry). `index.html` research-preview text updated.
- **Torch profiler is not usable on this XPU stack.** A131 (full-request
  trace) tripped the 12 GB memory floor; A136 (12 bounded iterations)
  captured, then the Kineto XPU profiler crashed the worker on stop
  (`PTI_ERROR_NOT_IMPLEMENTED` in `clearActivities`). Replacement: finer
  synchronize-based hooks (sub-operations inside QSA, GDN and MoE; patch
  drafted, applied after A133).
- **Packets built:** A133 (graph MTP2 battery, capture [1, 2, 3], selectors
  at three rows), A138 (MTP2 eager trace at 2048), A134/A135 (fixed
  realistic suite on the MTP0 and MTP1 identities for LocalMaxxing), the
  attestation builder `tools/build-q38-flash-next-promotion-attestation.py`.

## Late morning

- **A133: MTP2 lossless on the graph line.** Every pin equal to the MTP0
  line; short `32.21/37.03/32.00` (1.42x), exact-2K `8.09/7.37`, exact-4K
  `7.37/7.30`; acceptance 984/1122. The selectors generalize to three
  verifier rows. Certification pair A139/A140 built (verifier requires
  size-3 graph dispatches).
- **Realistic suite (LocalMaxxing gate):** A134 on the promoted MTP0
  identity (overlay at 2169dbfe) running; A135 (MTP1 identity, 1b2a17c1)
  next.
- **LocalMaxxing: first Flash-Next approval.** A134 ran the fixed realistic
  suite on the promoted MTP0 identity (gate passed, cache zero, 12/12):
  14.433684 tok/s class-balanced median (all-prompt 14.757), submitted as
  `cmtn32b2w000tmm01t7j2wlpn` and approved. Ledger, packet, family page and
  index updated. vLLM XPU payloads need `--engine-name vllm`, KV dtype
  `auto`, attention backend `triton` and the frozen server command as the
  snippet (`patch-localmaxxing-payload.py` step in the post-run script).

## Afternoon and evening (two more silent host freezes: 11:25 and 22:12)

- **Freezes:** the host froze at 11:24:57 (A141 launching) and again at
  22:12:29 (A143 relaunch, during the launcher's host reset, no engine
  process yet). Four silent freezes in two days, all inside the launcher's
  reset-then-start window, nothing in the journal, PCIe error counters
  zero. Frozen directories are kept as `*-frozen-1122` and `*-frozen-2212`.
- **A135 (realistic suite on the MTP1 line):** outputs identical to the
  approved MTP0 line 12/12, but 8.66 tok/s class-balanced against 14.43;
  withheld from LocalMaxxing.
- **A141/A142 (eager sub-operation split, M=2 vs M=1):** the MoE block
  pays 130-155 ms of the 166 ms two-row delta; the serial verifier GDN
  path about 45 ms; QSA and the hyperconnection mix near-flat.
- **A143 (request-shape matrix):** every request shape steps at 120-220
  ms per size-2 step on real prompts. The frozen client's short bench
  makes the model emit ` benchmark benchmark ...`, so its 22.66/27.15/32.2
  tok/s rows are degenerate-output rows; the realistic suite is the speed
  on text, the MTP lines are 0.60x on text, and the two-row cost is an
  M=2 MoE cost rather than a depth cost. Short-context MTP claims
  withdrawn; MTP2 certification (A139/A140) on hold.
- **A146/A145 (graph MTP0, control vs MoE skipped):** 72.7 ms per step
  with the MoE block, a flat 19.1 ms without it (46 tok/s): the MoE block
  is three quarters of the promoted decode step and all of its variance.
- **A147 (platform XPU FP8 MoE backend):** negative, the overlay's backend
  and the staged kernel package disagree on the interface; needs a rebuild
  plus the block-FP8 scale path.
- **Kernel lever identified:** the Triton fused MoE at M=1 launches about
  100 valid programs per GEMM per rank with split-K forced to 1. A
  deterministic split-K variant (partials to a workspace, fixed-order
  reduce, env `VLLM_XPU_MOE_SPLIT_K`) is written and dry-run; the offline
  equivalence-and-timing bench `tools/equivalence-and-timing-moe-splitk.py`
  is committed. A144 (graph MTP1, MoE skipped) and A148 (only the two
  GEMM launches skipped) are queued to finish the attribution.
