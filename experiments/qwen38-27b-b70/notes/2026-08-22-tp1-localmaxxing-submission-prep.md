# TP1 27.82 LocalMaxxing submission prep + MTP-row withdrawal

Date: 2026-08-22

Status: **evidence assembled; two human actions remain.** This note stages
everything for the TP1 submission and the invalidated-MTP-row withdrawal.
It performs neither: both need the LocalMaxxing credential (never touched
or printed by the agent) and the human category decision.

## Ready result

Qwen3.8 27B Q4_K_M target-only, one B70 (GPU0), no speculation.
Conventional 99-interval median **27.813629 / 27.824790 tok/s** across two
fresh cold suites, 24/24 oracle-exact output hashes, `cached_tokens=0` on
all requests, full quality battery pass. This is +6.8-7.0% over the
day-open 26.05 baseline, all bit-exact.

## Provenance snapshot (all in-repo, pinned)

- Source: mndodd `intel-sycl-optimization` base
  `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` + the lab TP1 fusion stack on
  `main` (lane tree `llama.cpp-q38-tp1-lane`, HEAD `fa0f3b25a`).
- Model: `Qwen3.8-27B-Q4_K_M.gguf` SHA-256
  `31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`,
  18,973,870,432 bytes.
- Final captures:
  `experiments/qwen38-27b-b70/data/2026-08-21-q4km-tp1-gpu0-final-{i,j}.json`.
- Baseline: `...-baseline-{a,b}.json`; quality:
  `2026-08-21-qwen38-q4km-tp1-quality-battery-result.md`.
- Lever ladder (each bit-exact): gdn-io -> conv-io -> qk-norm-rope, notes
  `2026-08-21-qwen38-q4km-tp1-{gdn-state-io,conv-state-io,...}-result.md`.
- Runtime door set + service environment captured in the server script
  `run-qwen38-q4km-tp1-gpu0-server.sh`.

## Human action 1: category check before submit

This is a ONE-B70 target-only result. Confirm the LocalMaxxing 1-GPU
category is the right bucket (the promoted 49.72 tok/s Q4_K_M row and the
101.9 MTP rows are TWO-GPU / speculative - different categories). Do not
submit the one-card number into a two-card board.

## Human action 2: withdraw the invalidated MTP rows

Earlier MTP endpoint rows `101.922` and `100.497` were later invalidated
(runtime nondeterminism: 21-23/25 pairwise parity; not token-reproducible
records). Withdrawal-note text for the LocalMaxxing entry:

  "Withdrawing these MTP5 rows: subsequent dual-view verification showed
  only 21-23/25 pairwise token parity across arms and 15/25 vs the
  target-only oracle, so they are research-anchor measurements, not
  reproducible records. The reproducible one-B70 target-only Q4_K_M result
  (27.82 tok/s, 24/24 exact) is submitted separately in its own category."

## Boundary

The agent will not run the LocalMaxxing API, read
`/home/steve/.config/localmaxxing/api_key`, or choose the category. When
you are ready, the submit + withdrawal are yours; everything above is
staged to make them one step each.
