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
