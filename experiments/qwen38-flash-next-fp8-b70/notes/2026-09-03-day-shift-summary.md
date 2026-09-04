# Day-shift summary, 2026-09-03 08:45 to about 13:45 EDT (four-B70 host)

The user's brief: every published recipe must be complete and reproducible
by a third party; keep optimizing Flash-Next (faster, lossless, and faster
to iterate); publish a host-tuning guide; general improvements welcome.

## Recipes and the site

- Recipe completeness audit over all 30 `repro/` lanes, `index.html`,
  `README.md`, `models/*.html` (filed at
  `audits/public-closure/2026-09-03-recipe-completeness-audit.md`). Fixed
  the same morning: the guide validator was failing at HEAD (an undeclared
  Laguna dependency from the previous night's fix); the rapid-snapshots
  directory is now catalogued with a README; 15 guides carry certification
  banners; five scripts lost hard-coded lab paths; the R62 base-image tag is
  documented on the published-binary route; the sitemap lists every model
  page; the R139 release's 14 assets are hash-bound in the FP8 publication
  manifest (`chain_releases`) and re-verified by the daily remote audit; the
  closure scanner now scans every lane (non-package lanes informational).
  All validators and both closure checks pass.
- New public guide: `learn/host-tuning.html` (Guide 10): fast versus slow
  hosts, graph on/off with trade-offs, the five-minute submission probe,
  and every host fix with its measured effect (speed, stability, capacity,
  or neutral). The 27B FP8 recipe README links to it; a reply for the X
  user who could not replicate the 27B result was drafted for the user.

## Flash-Next: the deterministic line is promoted

- A73 and A78 (two fresh servers, 4352 tokens) passed the whole frozen
  client with identical outputs: short center `22.66 tok/s`, exact-2K
  median `13.99`, exact-4K median `12.78` (native eager 4K: `5.27`); the
  exact-4K hash `c6193cc6...` has four servers, the exact-2K `afffd211...`
  seven. Recorded in the results packet and CURRENT.md as the lab's TP4
  record (decision memo option (a); native records untouched); family-page
  entries handed to Codex.
- A79: loading from the verified NVMe copy takes 66 s instead of 546 s;
  identical outputs; an attempt now takes 16 minutes instead of 24. Later
  packets derive from it. New one-command launch helper
  `q38-launch-frozen-attempt.sh` (preflight, swap reset, cache drop,
  validate, wrapper, driver).

## Flash-Next: MTP1 on that line

- A80/A81: MTP1 inside the full decode graph (capture sizes [1, 2], 32-block
  KV) needs about 4.5 GB more host RAM (supervisor floor now 12 GB). Short
  rows `38.8 tok/s` median (1.71x) on the MTP0 hash with 93% draft
  acceptance, quality identical, but the exact-2K/4K continuations diverge
  at near-ties and decode at about `7 tok/s` (half the MTP0 line) with
  double the TTFT.
- A83 (eager MTP1) reproduced A81 token for token with the same acceptance:
  the graph is not the cause.
- A84 (logprob probe): prefill and first token identical to the MTP0 line
  at depths 8/256/2048; from the second token on, top-1 logprobs drift by
  0.02-0.09 nats and every fixture diverges within 31 tokens. MTP1 is not
  lossless at any depth; the short-bench match was a peaky prompt.
- A85: the kernel source's serial-exact recurrent spec-decode path (sealed
  ad25aa9 stage, never measured before) runs inside the graph at `32.3
  tok/s` short (1.42x the MTP0 line), keeps quality identical, and moves the
  2K divergence from token 7 to the token-12 near-tie; 4K unchanged.
- Offline: a two-row BF16 oneDNN GEMM equals two one-row GEMMs bit for bit
  on every decode shape (`equivalence-m2-vs-m1-gemm-gate.py`); the MoE map
  already gives M=2 the M=1 config.
- A87/A88/A89: a port of the 27B lane's serial verifier-row flash
  attention (overlay `d3a61403`, then registered in `envs.py` as
  `0a03a84c`) was launched three times on the A85 identity; the gate never
  fired and each run repeated A85 (short `30.7-38.0`, exact-2K
  `29a2947a...`). The `/proc` environment evidence that misled A88 was a
  process-title artifact. A90 (an entry diagnostic at the top of the base
  attention forward) showed that forward is never entered: the model's
  full-attention layers run its own query-sparse attention
  (`Qwen4ExpQSAAttention`, indexer top-k plus the Triton QSA kernel), so
  the port does not apply as written. The overlay keeps the flag-gated
  branch (inert here) and the diagnostics are removed (`c23ad8e1f`).
  Notes: `2026-09-03-tp4-mtp1-a87-a88-serial-attention-gate-notes.md`.

## Afternoon and evening: MTP1 made exact (A91-A113)

- **Method.** Per-layer repeatability traces at the first two-row
  verification step (positions 2048/2049, the same state and tokens as the
  MTP0 decode step) compared record by record against an MTP0 reference on
  every rank, plus offline two-row-versus-one-row gates for each component
  the traces implicated. Every MTP1 attempt keeps the deterministic
  identity (`VLLM_XPU_MKLDNN_DETERMINISTIC=1`, W13-N32 map, PLE-only UVA).
- **Cleared offline (bit-identical at M=2 vs 2xM=1):** BF16 oneDNN GEMMs on
  every decode shape, the block-FP8 oneDNN linear path on the layer-0 shapes
  (`equivalence-fp8-linear-m2-vs-m1-gate.py`), the Triton block-FP8 MoE
  under three configs, the hyperconnection mix GEMMs at their real shapes
  (2.8 M and 8.2 M elements without a flip), the QSA index side path (A93,
  A108), and the hyperconnection gate-mix and SiLU fallbacks.
- **Three row-count dependences found and fixed, each flag-gated in the
  overlay with the MTP0 line untouched:**
  1. the GDN spec-decode kernel (A96/A97): verifier rows now run through
     the ordinary decode kernel one row at a time with state copies between
     the spec columns (`VLLM_XPU_GDN_SERIAL_SPEC_DECODE`, overlay fd81d811;
     A100/A104 traces exact through the recurrent core);
  2. the XCCL all-reduce (A104 vs A105; four-card probe
     `equivalence-tp4-allreduce-m2-vs-m1-probe.py`: a [2,N] all-reduce
     differs bit for bit from two [1,N] all-reduces at every width):
     row-wise all-reduce for 2..N-row inputs (`VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS`,
     overlay 8ca2cbc2; A106 exact through layer 42 at both rows);
  3. the hyperconnection grouped RMSNorm torch fallback (A110 vs A111 with
     QSA-layer records, overlay 76b787e2; `equivalence-hc-torch-fallback-m2-vs-m1-gate.py`:
     the `mean` over [rows, 4, 2560] flips one BF16 element in 1.5% of
     draws): per-row variance (`VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS`, overlay
     1b2a17c1).
- **A112 (eager MTP1, three flags):** zero numeric differences against the
  MTP0 reference through all 48 layers and the model output, both verify
  rows, all four ranks; exact-2K hash `afffd211...`, the MTP0 authority.
  Note: `2026-09-03-tp4-mtp1-a104-a105-allreduce-localization.md`.
- **A113 (full-decode-graph MTP1 battery, capture [1, 2], three flags):**
  short rows exact on the MTP0 hash at `31.2/34.7/31.3 tok/s` (MTP0 line
  center `22.66`); depth rows and quality recorded below when complete.
- **Host:** two silent freezes at worker initialization (16:44 during the
  first A112 launch, 18:12 during the first A113 launch), no kernel
  message either time; the user reset the host. After each reboot: results
  drive remounted (`ntfs-3g`), the four B70s reloaded under `xe` because the
  display driver had taken card1, tuning reapplied, links verified at
  16 GT/s x16. A102 was a memory-PSI guard trip during shard loading
  (host noise); A103 a packet-generation slip (MTP0 packets must come from
  the A96 generator).
- **Packets ready:** A114, the first frozen MTP1 client (A113 identity,
  receipts for `mtp=1`, KV 376569856, capture [1, 2], the three selectors;
  verifier `verify-q38-a114-fullgraph-runtime.py` requires size-1 and
  size-2 FULL dispatches; output pins unchanged).

## Standing

The deterministic MTP0 full-decode-graph line is the record. MTP1 on that
line is now bit-exact with it at the verification step (A112) and, in the
full decode graph, reproduces the short-context hash at 1.4x (A113 short
rows); the depth rows and quality of A113 decide whether A114/A115 (the
frozen MTP1 client and its fresh-server repeat) become the promotion pair.
