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
