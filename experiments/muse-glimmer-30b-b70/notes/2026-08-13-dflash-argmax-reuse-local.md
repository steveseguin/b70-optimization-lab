# Reuse local ARGMAX winners in TP maxloc

Date: 2026-08-13

## Decision

Retain the default-off local-winner path as the fastest measured exact stack:
**`73.731 tok/s`** versus pooled rescan controls at `73.001 tok/s`
(`+1.000%`).  All target outputs are canonical.  Treat the increment as a
proposal-path plus kernel change, not a clean 1% device-time claim: the code
arm accepted two more draft tokens and supplied most of the throughput delta.
No drafter training was performed.

The prior communicator received each device's completed local ARGMAX tensor but
ignored it, rescanning every vocabulary shard to recover the same local winner
and value.  The candidate reads the local winner index, gathers only its one
logit value per row, and then runs the unchanged recursive-doubling global
maxloc.  It is gated by `GGML_SYCL_COMM_ARGMAX_REUSE_LOCAL=1`.

## Final C/A/C

| arm | prose | code | JSON | mean |
| --- | ---: | ---: | ---: | ---: |
| rescan control before | `51.926` | `75.454` | `91.820` | `73.067` |
| reuse local winner | `51.933` | **`77.628`** | `91.632` | **`73.731`** |
| rescan control after | `52.047` | `75.090` | `91.670` | `72.936` |

Candidate hashes are canonical: `914f754747d0edaa`, `cf2b2c4fd9e36fe5`, and
`4f813a9706abc163`.  Prose/JSON candidate acceptance matched the controls at
`172/207`; code changed from `197` accepted tokens and `811` drafted in both
controls to `199/781`.  Since the target verifies every proposal, this changes
performance but not emitted bytes.  The proposal difference may indicate that
rescanning the source after the local graph is not equivalent to consuming the
materialized ARGMAX result; it was not attributed more narrowly here.

Source commit: `/home/steve/src/llama.cpp-muse-100` `51b93f8a0`
(`sycl: reuse local argmax winners in maxloc`).  A short three-class smoke
passed before the full run.

Evidence:

- final JSONL:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-argmax-reuse-local-final-ab-20260813.jsonl`,
  SHA256 `982a6199d37e5dca2bd612689169ab4aec9cc9bb3e773817550e2a23db2e513a`;
- final identity:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-argmax-reuse-local-final-ab.json`;
- smoke identity:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-argmax-reuse-local-smoke.json`;
- restored production health:
  `data/muse-health-20260813-dflash-argmax-reuse-local-final-restore.json`.

The source rebuilt through `llama-server`, and `git diff --check` passed before
the focused commit.  Production was restored without reboot and passed the
full model/cache-zero code/vision gate.  The TP2 production fleet was not
changed.
