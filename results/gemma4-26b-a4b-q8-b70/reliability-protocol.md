# Gemma 4 26B Q8 Reliability Protocol

Status: active. Use this before claiming micro-improvements near the current
`124.97714084813418 tok/s` record.

## Problem

The current final-postnorm Gemma 26B Q8 lane is valid but noisy. Single-run
medians are not reliable enough to judge small changes.

The 2026-07-01 same-GPU thermal sweep ran the exact promoted recipe four times
on GPU0 with telemetry:

- run medians: `115.515`, `119.019`, `114.520`, `120.202 tok/s`;
- run-median CV: `2.324%`;
- p90 pairwise absolute run-median delta: `4.409%`;
- active core max: `77-78 C`;
- active memory max: `86-90 C`;
- no thermal-throttle samples.

This means a one-off `+1%`, `+2%`, or even `+4%` result can be ordinary
same-recipe variance. Treat single-run record-family spikes as candidates for
confirmation, not as proof of a source or config win.

Evidence:

- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-thermal-variance.md`
- `data/gemma4-q8-finalpostnorm-thermal-repeatability-analysis-20260701.json`
- `data/gemma4-q8-finalpostnorm-thermal-repeatability-analysis-20260701.md`

## Tool

Use the paired analyzer:

```bash
cd /home/steve/qwen36-results-main
scripts/analyze-gemma-realistic-ab.py --help
```

Same-recipe repeatability:

```bash
scripts/analyze-gemma-realistic-ab.py \
  --same data/<run-a>/summary.json \
  --same data/<run-b>/summary.json \
  --same data/<run-c>/summary.json \
  --same data/<run-d>/summary.json \
  --out data/<label>-repeatability.json \
  --markdown-out data/<label>-repeatability.md
```

Control vs candidate:

```bash
scripts/analyze-gemma-realistic-ab.py \
  --control data/<control-1>/summary.json \
  --control data/<control-2>/summary.json \
  --candidate data/<candidate-1>/summary.json \
  --candidate data/<candidate-2>/summary.json \
  --out data/<label>-paired-ab.json \
  --markdown-out data/<label>-paired-ab.md
```

The script accepts either wrapper `summary.json` or direct
`realistic-suite.json` paths. It loads per-prompt timings, pairs prompts by
`prompt_sha256`, and bootstraps the candidate/control ratio across matched
prompts and repeats.

## Standard Decision Rule

For micro-changes on the current short-decode record lane:

1. Every candidate and control run must pass the fixed realistic final gate.
2. Every prompt must report `cached_tokens=0`.
3. The candidate must keep the same Q8 target/verifier and quality lane.
4. The paired bootstrap 95% lower bound of the median candidate/control prompt
   ratio must be above `+1.0%`.
5. The candidate must not materially regress p10, full512 after-TTFT, wall
   full512, TTFT, canary reliability, or thermal/frequency conditions.
6. If the result would become a LocalMaxxing headline, run an independent
   full512 confirmation after the A/B screen and submit only if it beats the
   existing matching record under the fixed-suite policy.

Default analyzer rule:

```text
candidate_win only when median paired ratio 95% lower bound > +1.0%
```

If the median ratio is positive but the lower bound is not above `+1.0%`, label
it `inconclusive_positive` and either collect more paired blocks or close it as
variance. Do not submit it.

## Run Design

Use paired, same-window blocks instead of historical comparisons.

### Env-only Candidate

Use ABBA or BAAB on the same GPU when practical:

```text
GPU0: control -> candidate -> candidate -> control
GPU1: candidate -> control -> control -> candidate
GPU2: control -> candidate
GPU3: candidate -> control
```

This cancels time drift, temperature drift, and GPU-specific behavior better
than comparing one candidate run against last night's best control.

### Source Patch Candidate

Keep two explicit binaries or source states:

- `control`: last promoted build;
- `candidate`: patched build.

Do not edit the active source mid-block unless the patch is snapshotted first.
Prefer two build directories and pass `LLAMA_SERVER=<path>` into the same
wrapper so launcher behavior stays identical.

### Four-GPU Use

For fast screens, use all four B70s as independent blocks:

- two GPUs start with control;
- two GPUs start with candidate;
- then swap assignments for the second block.

This is better than running four candidate lanes and comparing to an old record
because it creates same-window control data.

## Promotion Ladder

1. **Smoke:** strict canary / short run to catch correctness bugs.
2. **Screen:** paired A/B with the fixed realistic suite; use the analyzer.
3. **Confirm:** repeat the paired A/B if the screen is positive but CI is wide.
4. **Promote:** full512 fixed-suite confirmation, exact canary scale, telemetry.
5. **Submit:** LocalMaxxing only after the promoted result beats the matching
   prior record and all validity fields are checked.

## What Not To Do

- Do not compare a candidate against the historical `124.977` outlier alone.
- Do not promote a single-run candidate because it is `+1-4%`.
- Do not average warmed/history/n-gram/cache-reuse runs into fresh throughput.
- Do not change canary scale, max tokens, prompt suite, cache mode, target
  quantization, or telemetry conditions and call it an A/B.
- Do not discard slower same-recipe repeats unless a documented runtime failure
  or validity failure explains them.

## Current Noise-Floor Examples

Thermal repeatability analysis:

```text
runs: 4
run medians: 115.515, 119.019, 114.520, 120.202
run-median CV: 2.324%
pairwise abs delta p90: 4.409%
```

Fake A/B split of the same thermal runs:

```text
control medians: 115.515, 114.520
candidate medians: 119.019, 120.202
median paired ratio 95% CI: -1.186% / +3.057% / +7.067%
decision: inconclusive_positive
```

Even this cherry-picked same-recipe split is not a valid win because the lower
bound crosses negative. That is the intended bar for future micro-changes.
