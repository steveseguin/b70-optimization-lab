# FP8 27B review campaign: preregistration (2026-09-16)

Runner: `scripts/run-20260916-fp8-review-campaign.py` (one unattended run under `systemd-run --user`, unit
`fp8-review-20260916`). Output: `/mnt/fast-ai/bench-results/fp8-review-20260916/`.

## Questions

1. **Is the published one-card package really lossless and deterministic on a longer session than its tests used?**
   The one-card work (September 15-16) gated depth 5 on the 12-prompt strict suite, a 2K-12K context screen, a chat
   quality suite and a 21-request no-MTP replay. It never ran the 64-prompt sequential oracle that caught the two-card
   depth-2 "phantom first token" on September 3 (a scheduler bookkeeping defect under async scheduling, which this
   package also runs). This campaign runs the shipped `serve.py` for both profiles and gates them against a same-image
   no-MTP reference on: 64 prompts one at a time, then two queued 64-prompt passes; the strict suite; the context screen
   with two repeats; the chat quality suite with two repeats; the 21-request logprob replay at depth 5; a clean stop.
2. **Can the two-card lane reclaim MTP depth 5 (86 tok/s in early September) on the R310 runtime?** The two-card
   recipe was frozen at depth 1 (54.8 tok/s) because deeper drafts failed the sequential oracle on the R156 image.
   Since then the lane moved to vLLM 0.29 (R304) and gained the one-card identity fixes (r309 shapes, R310 fences,
   decode-identical verifier rows). Candidates: depth 5, 4, 3 with the INT4 draft shortlist; depth 1 with the shortlist;
   depth 1 as the same-session control.

## Gates (identity is the gate; speed is recorded)

- Same-image no-MTP references generated in this run (`tp1-mtp0`, `tp2-mtp0`); the two-card no-MTP strict run is also
  compared with the frozen two-card control to tie R310 to the qualified R304 arithmetic.
- A candidate passes only if every section is exact: sequential oracle 64/64, every queued pass 64/64 with cache zero,
  strict 12/12, context screen passed against the reference, chat quality baseline match, and (one-card recommended)
  zero token and zero logprob differences in the replay.
- No speed verdict from one server; the strict rates here are recorded next to the existing pairs.

## Abort and safety

- Any kernel GPU fault line (the packages' fault regex) halts the campaign; nothing is retried and the service is not
  restored by the runner.
- A server that fails to reach ready is recorded and skipped; no restart.
- The two-card service is stopped once at the start (after it is ready) and restored once at the end by the package
  launcher in its own unit, followed by a strict parity check against the frozen control.
- No power, driver, swap or cache settings are touched.

## On pass

- One-card: the package keeps its claims; the sequential-oracle and replay receipts are added to the recipe evidence.
- Two-card: the deepest depth that passes every gate becomes the candidate for a second fresh-server pair before any
  publication; depth 1 stays published until then.
