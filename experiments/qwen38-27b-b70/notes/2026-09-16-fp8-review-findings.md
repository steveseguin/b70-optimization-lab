# FP8 27B review, 2026-09-16: one-card package re-checked, two-card depth reclaim

Independent review of the September 15-16 one-card FP8 work, followed by one unattended campaign
([preregistration](2026-09-16-fp8-review-campaign-prereg.md),
[runner](../scripts/run-20260916-fp8-review-campaign.py), raw root `/mnt/fast-ai/bench-results/fp8-review-20260916/`,
receipts under [data/2026-09-16-fp8-review](../data/2026-09-16-fp8-review/)).

## What the review found before any GPU work

1. **A missing gate.** The one-card depth-5 package was qualified on the 12-prompt strict suite, a 2K-12K context
   screen, a chat quality suite and a 21-request no-MTP replay. It was never run through the 64-prompt sequential oracle
   that caught the two-card depth-2 "phantom first token" on September 3 (a scheduler bookkeeping defect that appears
   only after dozens of back-to-back requests). The package runs vLLM's async scheduling, the same mode that defect
   needed: vLLM 0.29 counts `qwen3_next_mtp` as an Eagle-type method and enables async scheduling for it by default.
2. **A launcher that only starts on this host's Docker.** Both package launchers compared `docker image inspect
   --format {{.Id}}` with the registry manifest digest. That equality holds only under Docker's containerd image store
   (this host). Under the classic image store, still the default on hosts upgraded from older Docker, `.Id` is the
   config digest (`845f559e…` for R310) and the launcher refuses to start with "Pull the pinned runtime first".
   Fixed in the one-card `serve.py` (`local_image_id()`: accept `.Id` equal to the pin or the pin listed under
   `RepoDigests`; the resolved local ID is recorded in `state.json` and used for container ownership checks). The
   two-card launcher (`serve.py` and the shared `run-server.sh`) has the same defect; those files are pinned by frozen
   evidence and are fixed with the two-card update below.
3. **Stale wording.** The package summary (and therefore the public model page) still said 13,824 tokens of context
   after the default moved to 16,384 on September 16. Fixed in `package.json`; pages regenerated.
4. **The draft shortlist is honest but worth stating plainly.** The 67,248-row draft shortlist was built from token
   frequencies over the lab's own text, system documentation and the image's Python sources (99.5% coverage of the
   suite output). It only limits what the draft may propose; the target still scores every token with its full head,
   so it cannot change an answer. It can flatter the benchmark's acceptance rate a little relative to unrelated text.
5. **The reference chain is sound.** Every one-card comparison in the package evidence used the R309+head-group no-MTP
   run (`fp8-tp1-35`) as its reference; the R310 no-MTP run (`fp8-tp1-54`) matches it 12/12, so the comparisons are
   effectively same-image.

## One-card package, re-tested through the shipped launcher

Server: `packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py start --profile recommended` (R310, 16,384 context, MTP
depth 5, INT4 draft shortlist), one B70. Reference: a fresh R310 no-MTP server in the same run (`tp1-mtp0`).

| Check | Result |
| --- | --- |
| 64 prompts one at a time, vs no-MTP one at a time | **64/64** identical |
| Two more passes of the same 64 prompts, queued all at once | 64/64 and 64/64, cache zero |
| Strict 12-prompt suite vs the R310 no-MTP strict run | **12/12**, 53.31 tok/s (published pair 53.58 / 53.45) |
| 2K/4K/8K/12K prompts, three content types, two repeats, vs no-MTP | passed, every continuation identical |
| Chat quality suite (7 exact cases, repeat, 8K needle) vs no-MTP baseline | matched |
| 21-request replay at depth 5 with logprobs | zero token and zero logprob differences |
| `status`, then `serve.py stop` | clean, container removed |

Prefill and writing speed after 2K-12K prompts matched the published points (2,024 tok/s prefill at 2K, 56.5 tok/s
writing). **The recommended one-card profile holds up.** The `no-quantization` profile was not re-run in this
campaign (my runner reused a port too soon and its server never started); its existing strict 12/12 evidence stands
and the sequential oracle for it is queued with the context-length work.

## Two-card depth reclaim

Two B70s, R310 image, 33,024-token context, one user. Reference: a fresh R310 no-MTP server in the same run
(`tp2-mtp0`), which matched the frozen R304 two-card control 12/12 on the strict suite at 33.04 tok/s, so the new
image's arithmetic is the qualified one. Every candidate below passed **all four gates**: strict 12/12 identical to
no-MTP, 64/64 on the sequential oracle and 64/64 on each of two queued 64-prompt passes (cache zero), the 2K/8K/16K
context screen with every continuation identical to no-MTP, and the chat quality suite matching the no-MTP baseline.

| Server | Strict writing speed | Prompt reading 2K / 8K / 16K | Writing after 2K / 8K / 16K input |
| --- | ---: | --- | --- |
| No MTP | 33.04 | 3,763 / 3,535 / 3,384 | 32.7 / 31.8 / 31.0 |
| Depth 1, full-vocabulary draft head (the September 14 recipe) | 54.90 | 3,648 / 3,435 / 3,288 | 54.5 / 55.6 / 53.0 |
| Depth 1 + INT4 draft shortlist | 55.25 | 3,657 / 3,437 / 3,289 | 54.8 / 56.1 / 53.3 |
| Depth 3 + shortlist | 80.44 | 3,652 / 3,443 / 3,286 | 79.0 / 92.5 / 83.0 |
| Depth 4 + shortlist | 83.97 | 3,650 / 3,437 / 3,283 | 80.3 / 109.1 / 89.8 |
| **Depth 5 + shortlist** | **88.32** | 3,642 / 3,436 / 3,282 | 88.0 / 114.0 / 96.3 |

All speeds are tokens/s; strict is the class-balanced median of tokens 1-100 over the fixed 12-prompt suite. The
depth-1 control shows the runtime change itself costs nothing (54.90 here against 54.80 on the R304 service the same
morning). Depth 5 is +61% over the published recipe and above the September 4 depth-5 record (86.18) that was
withdrawn for the phantom first token; that phantom did not appear in 192 depth-5 answers here, nor at depths 3 and 4.

**Decision.** The two-card package moves to MTP depth 5 with the draft shortlist on R310 (`serve.py` rewritten in the
one-card style, `depth-1` kept as a profile, image-identity check fixed for both Docker image stores, compose
regenerated from the launcher's own `docker run` argv). The pair rule is satisfied by the acceptance replay of the
package launcher from an anonymous public-source download (`run-fp8-tp2-acceptance-session.py`, frozen by
`collect-fp8-tp2-acceptance-evidence.py`), which is the second fresh depth-5 server.

Receipts: [data/2026-09-16-fp8-review](../data/2026-09-16-fp8-review/) (`results.json` has every gate per stage).

## Left open

- Depth 6 on two cards (one card showed a small first-100 gain and a small whole-answer loss).
- The one-card `no-quantization` profile's sequential oracle (the recommended profile passed; the runner's port
  reuse skipped this one).
- One-card context above 16,384 tokens: at depth 5 the card has 2.55 GiB left for KV (about 20K tokens at this
  model's page layout, 132 KB per token including page padding); probes at 24K/32K with a 2,048-token prefill chunk
  are queued in the follow-up runner. Any real gain needs freed memory (smaller prefill chunk, smaller draft head, or
  a page layout with less padding), not tuning.
