# Packet58aq result: the per-token publication drain costs 1.11 ms/token on the one-card record line; build brief written

Card 0, whole host, boot 2cba7160, 2026-10-19:
- smoke `packet58aq-smoke-A` 07:49–07:57 UTC, 12/12 exact;
- diagnostic `packet58aq-split-A` 07:59–08:11 UTC, one load, six views × 12 prompts, 32-token cap.

All 72 requests are exact vs `iq3-p49-split32-v1`. GPU fault count stayed 2. Codex was fully frozen during the diagnostic.

The line is packet58aj, the one-card record line (31.966820 tok/s): resident lookups, BF16 KV, 21.55 GB expert cache. This is a diagnostic only, never a speed result.

| View | Probe | Publication ms/token | Drain ms/token | Construction | Enqueue host | Wall ms/token |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A0 | control | 1.255 | 1.072 | 0.144 | 4.97 | 31.03 |
| U0 | zero-byte upload | 1.213 | 1.039 | 0.147 | 5.05 | 30.80 |
| S0 | no scatter | 1.231 | 1.071 | 0.142 | 5.04 | 30.72 |
| D0 | construction only, no device op | 0.145 | 0.000 | 0.139 | 4.97 | **29.69** |
| W0 | wait stamps | 1.247 | 1.071 | 0.138 | 4.99 | 30.64 |
| A1 | control | 1.252 | 1.071 | 0.142 | 4.95 | 30.80 |

Every view also runs a timed repair of about 1.09 ms/token, so the wall times include it in every arm.

Paired against both controls, conservatively, with publication cadence matched:

| Component | ms/token | Verdict |
| --- | ---: | --- |
| **device publication + drain** | **1.108** | **qualifies** |
| construction | 0.142 | below threshold |
| upload | 0.038 | below threshold |
| scatter | 0.019 | below threshold |

- The threshold is 0.67 ms/token, about 2%. Control drift is −0.003 ms/token (publication) and −0.22 ms/token (wall).
- The wall-clock difference agrees independently: D0 is 1.11–1.34 ms/token faster than the controls.
- The W0 wait envelope is 21.6 ms/token. That is the host blocking on device work (GPU-bound) and includes the inherited 1 ms poll sleep; it is not kernel time.
- Enqueue host work is 5.0 ms/token. It overlaps device execution, so it is not a lever by itself.

**Decision:** the analyzer wrote `BUILD-BRIEF.md` (device_publication_and_drain). Its contract:
- keep dependency ordering and staging lifetime through later same-queue work, instead of a blocking poll at publication;
- never remove a reader fence or reuse staging early;
- preserve revocation and fill completion;
- measure the replacement overhead;
- byte parity, the unchanged oracle and two fresh-process repeats before any speed claim.

The ceiling is about +3.6%: 31.03 → 29.92 ms/token if the whole 1.11 ms goes, which would be about 33.1 tok/s on the record line. Next is packet58ar: build plus a one-load kill-test v5, with no separate smoke.

Evidence (compact files tracked; raw streams local):
- `experiments/own-xpu-runtime/stage2/packet58aq-onecard-split/screen/evidence/card0-58aq-split-a/resident/WSCREEN/run/{summary.json,BUILD-BRIEF.md,receipt.json}`;
- `smoke/WSCREEN/summary.json`.
