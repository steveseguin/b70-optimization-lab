# Proposal: one-launch verify for the two-card FP8 package (2026-10-17, owner decision)

**What it changes:** `packages/qwen38-27b-fp8-tp2-b70` checks each step's drafted tokens with six separate attention
calls per layer once a request passes 1,536 tokens (`b70_fa_verify_rows` 0.1.0). Version 0.2.0 with
`B70_FA_VERIFY_ROWS_ONE_LAUNCH=1` does the same rows in one launch, with the same arithmetic. On the research server
(R314, 262K window) it took 30 % off each writing step at 32K and 60 % at 246K, with all 14 long answers bitwise
equal and a 4,190/4,190 kernel census ([evidence](2026-10-17-fp8-writing-attention.md)). The package's window is
33,024 tokens, so its gain is the 2K-33K part. Rough expectation, not a result: little at 2K, 15-30 % per step at 16K.

**Public numbers that would change:** only the by-length writing curve, `package.json` `performance_profiles[0]`
(`r310-decode-vs-context-tp2-mtp5`: 87.96 / 114.01 / 96.29 tok/s at 2K / 8K / 16K). Unchanged: the 90.3 headline
(short prompts, under 1,536 keys), the depth sweep, depth-1's 54.9, no-MTP, prompt reading, multi-user.

**Scope:** the `recommended` profile only. depth-1 (2 rows) and multi-user keep their launch arguments byte for
byte. Multi-user drafts nothing, so the mode is unreachable there anyway (`b70_fa_decode_per_seq` hands one-row calls
through; its multi-row branch only fires when several users draft).

## Why the current release gates are not enough

None of them reaches the overlay. Strict-suite prompts are 48-78 tokens with answers of at most 512, so no more than
about 590 keys. Practical requests and the ladder stay at 256 or fewer. Only the 2K/8K/16K context screen and the
quality suite's 8K needle pass 1,536 keys. The census so far covered pages of 832 and 1,280 on R314. The package runs
`--block-size 64` on R310: same attention kernel (R314 rebuilt only the GDN kernels), but page 64 is unchecked.

## Gates, in order (about 35-45 GPU minutes)

1. Census on R310, card 0: `scripts/census-verify-rows.py --pages 64,832 --overlay <package overlay copy>`, about 2
   minutes. Any mismatch stops the change.
2. A research MTP5 server with the switch, through `scripts/fp8-gate-suite.py`: strict twice, context 2K/8K/16K and
   quality, against the no-MTP references (`/mnt/fast-ai/bench-results/fp8-review-20260916/tp2-mtp0-*`), about 12
   minutes. Its `container-final.json` becomes the new qualified receipt
   (`runtime_matches_qualified_depth5` in the collector compares the container's environment exactly).
3. A no-MTP reference at 24,576 / 30,720 / 32,768 tokens, then the candidate at the same lengths, about 12 minutes.
   There is no two-card no-MTP reference above 16K today. If they differ, a 0.1.0 arm (about 8 minutes) tells an old
   near-tie from the new mode.
4. The acceptance session from the pushed branch commit (`run-fp8-tp2-acceptance-session.py`), about 8 minutes.
5. CPU: a new evidence packet, the collector's DEFAULT repointed, `tools/test_fp8_serve.py` `FROZEN_SERVE_BLOB`
   updated, compose and model pages regenerated, every `guides.yml` line run locally, then merge.

**Files that would change:** the package overlay (0.2.0 copy) and its dist-info, `scripts/serve.py`, `compose.yaml`,
`package.json`, `README.md`; the generated catalog and pages (`packages/catalog.json`, `models/`, `index.html`,
`learn/hardware.html`); `run-fp8-tp2-acceptance-session.py` (pinned paths), `collect-fp8-tp2-acceptance-evidence.py`
(DEFAULT), `tools/test_fp8_serve.py`; a new packet and data folder; CURRENT.md. The work goes on a branch: the
source pins (`manifest.json` sha256 per file, `check_sources`) fail on any edit to serve.py or the overlay until the
new packet is in.

**Asked of the owner:** go or no-go for the package change. Gates 1-3 are research and can run before the answer;
gates 4-5 and the public numbers wait for it. The one-card package ships 0.1.0 too, with its own `paged_decode_multiq`
path past 4,096 keys; out of scope here.

## Gate 1 result (03:38 EDT, R310, card 0; `data/2026-10-17-verify-census/attn-r310.json`)

Census on the package image, split counts from the overlay file: one launch equal to the lone rows 6/6 at
**4,190 / 4,190** lengths for pages of **64** and of 832 (the other 19 per page are split-count boundaries, where it
falls back to per-row calls). The same as R314.

## Gates 2-3 (registered 03:45 EDT, before the run): `scripts/run-20261017-tp2-one-launch-gates.sh`

Servers: the comm-2 `tp2-ag-mtp5` research launch on R310 (the package's argv: block 64, 33,024 window, allgather
overlay), in order. R0: no MTP, a long reference at 24,576 / 30,720 / 32,768 tokens (the September long corpus; the
2K-16K corpus has only 22,933 tokens of code). C1: MTP5 + one launch, the gate suite (strict; context 2K/8K/16K;
quality; vs the 2026-09-16 no-MTP references), strict again, then the long lengths against R0. O1, only if C1's long
lengths differ: MTP5 on the per-row path, the same lengths.

- **Predictions:** C1 strict 12/12 twice, context exact, quality pass with baseline match, long lengths equal to R0.
  The context probe's writing speed (128-token answers) about the published 87.96 at 2K, 5-15 % above 114.01 at
  8K, 15-30 % above 96.29 at 16K.
- **Decision:** all exact: gates 1-3 pass and the proposal is ready for the owner (gates 4-5 wait for the go). If C1
  differs and O1 does not, the new mode is at fault and the change stops. If both differ, an old near-tie at those
  lengths is recorded, and the per-row path is no better.

## Gates 2-3 result (03:45-04:05 EDT, R310, both cards, kernel log clean; `data/2026-10-17-tp2-one-launch-gates/`)

| Gate | C1 (MTP5 + one launch) |
| --- | --- |
| Strict, run 1 / run 2, vs the no-MTP reference | **12/12 and 12/12**, 90.1 tok/s |
| Context 2K / 8K / 16K, two repeats, vs the no-MTP reference | **exact**, 18 rows |
| Chat quality, vs the no-MTP baseline | **pass**, every answer matched |
| Long 24,576 / 30,720 / 32,768, two repeats, vs R0 (no MTP, recorded today) | **exact** |

O1 (per-row path) was not needed. Writing speed in the context probe (tokens 1-100 of a 128-token answer, median per
content type, then across types):

| Prompt | Published (`r310-decode-vs-context-tp2-mtp5`) | C1, one launch | Change | No MTP (R0) |
| ---: | ---: | ---: | ---: | ---: |
| 2,048 | 87.96 | 92.68 | +5.4 % | |
| 8,192 | 114.01 | 133.57 | +17.2 % | |
| 16,384 | 96.29 | 123.57 | +28.3 % | |
| 24,576 | | 80.14 | | 30.97 |
| 30,720 | | 80.87 | | 30.43 |
| 32,768 | | 97.33 | | 30.29 |

The 24K-32K rows use the September long corpus (different text from the 2K-16K rows), so the two sets are not one
curve. Predictions: 2K "about the published" (+5.4 %, a little more), 8K 5-15 % (+17.2 %, above), 16K 15-30 %
(+28.3 %, inside). Prompt reading unchanged.

**Decision (as registered): gates 1-3 pass.** The proposal is ready for the owner. Gates 4-5 (acceptance session from
a pushed branch commit, new packet, CI) and the public numbers wait for the go.
