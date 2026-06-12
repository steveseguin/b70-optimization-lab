# Qwen3.6 Hotset Split Floor Model

This is a CPU-only model from dry-run route windows. It does not claim
endpoint speed. It estimates whether a hot/cold split can survive the
extra launch penalty before a real XPU benchmark.

GEMM stages modeled per MoE layer window: `2`
Primary scenario: baseline `200.0 us`, launch overhead `10.0 us`

## Aggregate Windows

| source | mode | cases | hot cov min/mean | cold rows max | cold active max | table slots mean/max | extra launches mean | required body speedup |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| l20-promptclass-repetitive | compact | 6 | 62.5% / 83.3% | 48 | 34 | 0.31x / 0.38x | 2.0 | 1.11x |
| l20-promptclass-repetitive | full | 6 | 62.5% / 83.3% | 48 | 34 | 1.25x / 1.25x | 2.0 | 1.11x |
| l20-routecapture5 | compact | 5 | 82.0% / 85.5% | 23 | 16 | 0.31x / 0.31x | 2.0 | 1.11x |
| l20-routecapture5 | full | 5 | 82.0% / 85.5% | 23 | 16 | 1.25x / 1.25x | 2.0 | 1.11x |
| l9-promptclass-math | compact | 6 | 69.5% / 78.4% | 39 | 30 | 0.34x / 0.37x | 2.0 | 1.11x |
| l9-promptclass-math | full | 6 | 69.5% / 78.4% | 39 | 30 | 1.25x / 1.25x | 2.0 | 1.11x |
| l9-routecapture6 | compact | 5 | 75.0% / 87.0% | 32 | 22 | 0.29x / 0.34x | 2.0 | 1.11x |
| l9-routecapture6 | full | 5 | 75.0% / 87.0% | 32 | 22 | 1.25x / 1.25x | 2.0 | 1.11x |

## Interpretation

- l20-promptclass-repetitive compact-cold split needs stress validation: minimum hot coverage is only 62.5%.
- l20-promptclass-repetitive compact-cold split has enough table-slot shrink (0.31x baseline) to justify a maintenance-window microbench, but persistent/fused fallback remains the safer production target.
- l20-promptclass-repetitive full-cold split is a poor two-launch target: mean table slots are 1.25x baseline and every cold fallback adds launches.
- l20-routecapture5 compact-cold split has enough table-slot shrink (0.31x baseline) to justify a maintenance-window microbench, but persistent/fused fallback remains the safer production target.
- l20-routecapture5 full-cold split is a poor two-launch target: mean table slots are 1.25x baseline and every cold fallback adds launches.
- l9-promptclass-math compact-cold split needs stress validation: minimum hot coverage is only 69.5%.
- l9-promptclass-math compact-cold split has enough table-slot shrink (0.34x baseline) to justify a maintenance-window microbench, but persistent/fused fallback remains the safer production target.
- l9-promptclass-math full-cold split is a poor two-launch target: mean table slots are 1.25x baseline and every cold fallback adds launches.
- l9-routecapture6 compact-cold split has enough table-slot shrink (0.29x baseline) to justify a maintenance-window microbench, but persistent/fused fallback remains the safer production target.
- l9-routecapture6 full-cold split is a poor two-launch target: mean table slots are 1.25x baseline and every cold fallback adds launches.

## Break-Even Rule

- Full path body fraction is normalized to `1.0` for the selected MoE layer window.
- Split path must run at or below `1 - extra_launches * launch_overhead / baseline`.
- If that fraction is negative, a two-launch split cannot break even under that scenario.
- Because row math is unchanged, real wins must come from lower expert/table overhead, better packing, fewer memory round trips, or persistent/fused execution.

