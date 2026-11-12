# Round 19, gate tg104 + tg104b + tg104c (build tp104, 2026-11-12)

tp104 = tp103 + px-512 (`OWN_PX_BIG=1`: prompt blocks up to 512 tokens, each run as two halves of at most 256, so
no kernel sees more than 256 tokens) + px-move (`OWN_PX_MOVE` 0-3: where the overlapped pulls are queued) and
`OWN_PX_WGS` (work-groups per pull), all opt-in. Prompt-centred gate. Speed is judged only from unprofiled runs
alternated (profiled queues change two-queue overlap).

tg104 (01:06) ran stage 1 and the 3K traces through t3k_b301, then the host reset at ~01:14 during t3k_b300.
tg104b (09:23) resumed at t3k_b300 and the host reset again at ~09:24, early in the same run's prompt. tg104c
(09:44-10:58, ALLDONE) ran everything after t3k_b300 without it. t3k_b300 (blocks of 300 = halves of 150) is
banned: two resets in two tries, and no other run reset (see the host-reset section in the strategy notes).

## In plain words

- **Every trace identical, every answer the same.** Stage 1: h1 / h5 / h64 / h256 / h4 defaults; the overlap at
  36 (`OWN_PX_MIN=16`), at 512 with px-512, and with px-move. 3K traces against the tp84 reference: 256, px-512 x2,
  px-512 serial, 301 (blocks of 256 + rest), 256 with px-512's buffers, px-512 with fewer pull work-groups (w8, w4),
  px-512 with px-move. `OWN_PX_CHECK`: 0 bad blocks everywhere. All four guessing runs SAME AS the plain run, code /
  analysis guess logs equal to tg100's, and the guessing after a px-512 prompt read has the same guess log as after
  a plain one.
- **3K prompt read (256 answers, alternated x2):** plain blocks of 256 5.71 / 5.73 s; overlap at 256 5.67 / 5.69;
  **px-512 5.56 / 5.55 s (-2.8 %)**; px-512 + px-move 5.56; px-512 serial (no overlap) 5.93 / 5.92; fewer pull
  work-groups: w8 5.67 / 5.68, w4 5.80 / 5.78 (worse). Predicted for px-512: ~5.44 (5.38-5.52): the gain is under
  the prediction. Steady state (without the first block, which includes kernel builds): ~0.39 s per 256 tokens
  against ~0.44 s at blocks of 256 (-11 %); the first 512 block costs 0.87 s against 0.47 s for the first 256 block.
- **Plain writing unchanged:** tp103 103.56, tp104 103.48 tok/s.
- **Guessing:** code 143.25, analysis 159.05 tok/s (tp104 defaults); after a 3K read: 142.52 (prompt at 256),
  147.39 (prompt at 512 with the overlap; same guess log; the difference is the engram rows' read time, 896 us
  against 197 us per step, page-cache state, not the overlap).

## Decision

px-512 is exact and -2.8 % on the 3K read. It stays opt-in until the peer-traffic setting (iommu=pt, reboot
approved 2026-11-12) is in and measured, because the host resets point at card-to-card reads. Then decide the
default with the after-numbers (gate tg105pt).

## Files

`tg104-summary.txt` (all three parts: tg104, tg104b, tg104c), `spec/` (guess logs). Scripts in
`../round18-scripts/strategy/` (build104*.sh, tg104.sh, tg104b.sh, tg104c.sh, tg105pt.sh, probe0113.sh,
probe0924.sh, pt/).
