# B70 2.8 GHz frequency-lock screen

## Scope

The promoted Qwen27 TP2 record was tested with each candidate pair locked to
the B70's official 2.8 GHz maximum core frequency while the simultaneous
control pair retained the default `400-2800 MHz` range. The firmware power cap
remained `230 W`; attempts to change it were rejected or ignored and no
over-power result was run. Pair assignments were swapped and all cards were
restored on exit.

## Result

| Window | Locked pair | Default control | Delta |
| --- | ---: | ---: | ---: |
| locked GPUs 0,1 / control 2,3 | `93.859763` | `92.993467` | `+0.93%` |
| locked GPUs 2,3 / control 0,1 | `93.789878` | `93.785764` | `+0.00%` |

Pair-balanced mean was `93.824820` locked versus `93.389615` default,
`+0.466%`. Every row passed the strict fresh/cached-zero mechanics. Quality
was skipped because the change is output-neutral and the speed movement is
well inside endpoint variance.

## Decision

Do not promote the lock as a speed record. It may reduce low-frequency
variance in controlled diagnostics, but the 230 W cap already governs sustained
decode and the endpoint gain is not material. The reproducible harness retains
an unconditional trap that restores `400-2800 MHz` on every exit path.

Artifacts:

- `experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-frequency-lock-crossover-4gpu.sh`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-frequency-lock-crossover-20260711.json`.
