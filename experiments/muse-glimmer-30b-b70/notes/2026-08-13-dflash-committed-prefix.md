# DFlash committed-prefix processing

Date: 2026-08-13

## Result

This is a retained exact inference-path win. Delaying DFlash feature encoding
until target verification has selected the committed prefix, then processing
only those committed input rows, raised the fixed-suite mean from pooled
adjacent controls of `77.0998 tok/s` to `78.6840 tok/s`, or `+2.055%`.
No drafter weights changed and no drafter training was performed.

| Arm | Prose | Code | JSON | Mean tok/s |
| --- | ---: | ---: | ---: | ---: |
| control before | 54.722 | 79.488 | 96.630 | 76.9467 |
| committed-prefix candidate | 55.981 | 81.174 | 98.897 | 78.6840 |
| control after | 54.985 | 79.597 | 97.177 | 77.2530 |

All nine outputs matched the canonical hashes:

- prose `914f754747d0edaa`;
- code `cf2b2c4fd9e36fe5`;
- JSON `4f813a9706abc163`.

Drafted/accepted counts were also identical in every arm:
`1199/172`, `811/197`, and `684/207`. The comparison is therefore isolated
from proposal-history or acceptance drift.

Derived speculative-round costs were:

| Class | Rounds | Pooled control ms/round | Candidate ms/round | Saved |
| --- | ---: | ---: | ---: | ---: |
| prose | 84 | 55.560 | 54.440 | 1.119 ms |
| code | 59 | 54.549 | 53.453 | 1.096 ms |
| JSON | 49 | 53.915 | 52.828 | 1.087 ms |

The raw candidate mean is also above the previous exact campaign best of
`77.824 tok/s`, so `78.684 tok/s` is the new exact TP4 best. This remains well
below the honest `>100 tok/s` goal.

## Mechanism

The previous server path called `common_speculative_process` immediately after
target decode on the complete 16-row anchor-plus-draft batch. Rejected suffix
rows were then discarded after target sampling, despite already having been
encoded into the DFlash state.

Source commit `c9927d3e3` delays that call for one isolated linear DFlash batch.
After target sampling it presents only `accepted.size()` input rows: the anchor
plus the accepted draft prefix. Prompt, prefill, mixed-slot, and multi-slot
batches retain the original eager path. The experiment is default-off behind
`LLAMA_DFLASH_PROCESS_COMMITTED_ONLY=1`.

The first-hit server marker appeared in both the short smoke and the full
candidate log. The short 64-token smoke produced `68.412 / 111.693 / 216.229
tok/s`, but its acceptance was too high and its duration too short to use as a
performance claim. It was only a functional gate for the full C/A/C.

## Phase-budget evidence

Immediately before this experiment, the retained target-and-DFlash device
greedy stack was profiled with `LLAMA_SPEC_PROFILE=1`. At cumulative rounds 64
and 128 it reported:

- feature extraction: `0.20 / 0.18 ms/round`;
- DFlash encoder/injection: `3.41 / 3.55 ms/round`;
- draft proposal: `6.24 / 6.22 ms/round`.

The committed-prefix win recovers about `1.1 ms/round` from that encoder lane.
Even eliminating the remaining encoder and draft time entirely would not, at
the current acceptance rates, provide a defensible `>100 tok/s` result. A
larger exact verifier-kernel or acceptance-structure win is still required.

## Identity and evidence

- target: Muse Glimmer 30B BF16, TP4 tensor split;
- assistant: BF16 DFlash, width 15, `p_min=0`;
- greedy, parallel 1, prompt cache off, 256 generated tokens per fixed prompt;
- retained device-side batched distributed greedy sampling for target and
  DFlash, local-winner maxloc, oneDNN caches, shared BF16 conversion, and
  parallel meta submit;
- candidate-only flag: `LLAMA_DFLASH_PROCESS_COMMITTED_ONLY=1`.

Tracked artifacts:

- phase-profile config: `sweeps/20260813-target-greedy-spec-profile.json`;
- smoke config: `sweeps/20260813-dflash-committed-prefix-smoke.json`;
- full C/A/C config:
  `sweeps/20260813-dflash-committed-prefix-final-cac.json`;
- structured summary:
  `data/muse-dflash-committed-prefix-final-cac-20260813.json`;
- source snapshot:
  `patches/muse-glimmer-30b-b70/source-snapshots/20260813-muse100-dflash-committed-prefix.patch`.

External raw artifacts under
`/mnt/fast-ai/bench-results/muse-glimmer-30b/{sweeps,servers}/`:

- profile JSONL SHA256:
  `192b1af17c9be0f0cbce7024d72b47bdfac6e736e89f36dc897b051c43357298`;
- profile server log SHA256:
  `6e9e1c1675dad54f0df5d08af830dcfa79379f45dab536c69330305924688448`;
- smoke JSONL SHA256:
  `7262fbe41006d3bfc43d23659c2e171fba01920342bd0fc81aafa6d46e5b10ac`;
- full C/A/C JSONL SHA256:
  `563c6e4557bf8b6c93e0d8cfb7e39ed5b6d1b50ba65022f0307c63c34b5a939e`;
- full control-before/candidate/control-after log SHA256:
  `7579bcf8c800382eeb908e92161562168cd898a39696e26cc2664ea86acb8bf8`,
  `cecd1fb1afe683b1014bc99b9ede9fb874a4a62327d6de187e7300078022d3a5`,
  and `d4d762a87d70ac4c135cc98e90e7e44e37c3200be89046086d0a4499d09592b6`.

Production was restored without a reboot and passed the full model,
cache-zero code, and vision gate in
`data/muse-health-20260813-dflash-committed-prefix-restore.json`.

## Decision

Retain source commit `c9927d3e3` and promote `78.684 tok/s` as the current
exact campaign best. Keep the feature default-off until it receives the same
multi-slot and longer-run coverage required for production. Do not represent
this supporting win as a route that independently clears 100 tok/s.
