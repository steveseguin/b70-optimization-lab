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

## Standing

The deterministic MTP0 full-decode-graph line is the record. MTP1 is worth
1.4-1.7x at short context but is not lossless; the remaining difference is
inside the two-row verification step after the recurrent path is made
exact and the dense GEMMs are cleared; the next work is offline and per
component (QSA indexer/top-k and kernel with two rows, Triton block-FP8 MoE
at M=2, rejection sampler), the treatment the 27B lane received.
