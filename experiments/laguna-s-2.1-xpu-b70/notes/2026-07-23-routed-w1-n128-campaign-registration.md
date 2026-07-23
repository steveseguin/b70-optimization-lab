# Laguna routed-W1 N128 endpoint campaign registration

Date registered: 2026-07-23 America/Toronto

Status at registration: endpoint tools frozen and independently audited; no
campaign directory, service startup, endpoint generation, or LocalMaxxing
request exists for this campaign.

This note activates the endpoint experiment preregistered in
`2026-07-23-routed-w1-n128-endpoint-preregistration.md`. The sole treatment is
the exact M=8 routed-W1 workgroup N tile:

- control: `VLLM_XPU_LAGUNA_M8_W1_N_TILE=64`;
- candidate: `VLLM_XPU_LAGUNA_M8_W1_N_TILE=128`.

Every other source, model, runtime, benchmark, speculative-decoding, and
kernel setting is identical.

## Frozen campaign identity

- campaign root:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-endpoint-abba-8936aac-c59aaad-20260723T093923Z`;
- A1:
  `01-A1-control`;
- B1:
  `02-B1-candidate`;
- B2:
  `03-B2-candidate`;
- A2:
  `04-A2-control`;
- vLLM:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- XPU kernels:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`;
- frozen endpoint-tool commit:
  `73bd50099`;
- runner SHA-256:
  `ccf8da1924dfda527bcec40029cdba0b1718e474cbfde635f774603dde50c752`;
- analyzer SHA-256:
  `a8ec3d624709d64563e09b12ef6a52c563cd51cb97866c9148415f6499facade`;
- approved record floor:
  `33.89498511171744 tok/s`
  (`cmrx6p5dv001bo4017hb7sixz`).

The runner pins the canonical teacher, fixed 13-prompt suite, target and draft
model revisions and manifests, launcher, comparator, benchmark client, native
binaries, oneCCL, libfabric, component evidence, and every benchmark-sensitive
environment value. It rejects dirty source trees and records the main
repository commit used by every leg.

## Evidence required before endpoint execution

The exact N128 candidate passed:

- four-card changing-input raw exactness and all 31/31 A-B-B-A timing blocks
  per card, with 8.7271% mean isolated W1 improvement;
- four-card matched ComputeBasic counters, with 7.7158% mean counter-time
  improvement, higher EU activity and occupancy, lower stall, and zero spill
  proxies; and
- identical N64 W2 and gather kernel names and 13/13 call counts on every
  card.

Pinned aggregate evidence:

- component summary SHA-256:
  `bb48793e711cdb20889e888092344d35f0f3c7cb0e85bc120f63f51cff39b932`;
- counter/trace summary SHA-256:
  `677b69fe353056a8a7a9afff7e7e952fe337a6d605c326beb80ae5e0103b6e76`.

## Audited no-rescue protocol

The runner permits only the literal A1/B1/B2/A2 paths above. It uses a locked
append-only campaign journal, exact per-leg file manifests, and a SHA-256
chain from a fixed zero genesis. It rejects reuse, extra attempts, unexpected
files or directories, altered evidence, short inter-leg cooling, an active
service, busy devices, inherited benchmark-sensitive environment, and any
fifth or rescue leg.

B2 is impossible unless the independently generated phase-1 JSON, Markdown,
stdout copy, and atomic validity seal agree byte-for-byte and bind A1, B1,
their evidence chain, the journal, and both frozen tool hashes. The full
analyzer independently reconstructs the journal, manifests, request counts,
token arrays, canaries, metrics, timing, and comparison reports. It invalidates
stale seals before analysis and publishes a new atomic seal only after final
evidence rehashes succeed.

Independent blocker-only reviews of the exact frozen hashes found no
correctness blocker. Static checks passed Bash syntax, Python compilation,
Ruff lint and format, and whitespace validation. Synthetic and adversarial
tests passed the phase and full A-B-B-A paths and rejected token, metric,
request-count, treatment, ordering, gap, directory, journal, chain, artifact,
and record-floor drift.

## Formal execution

Run each leg from the repository root with a sanitized environment. Allow at
least 65 seconds after the prior leg's cleanup before invoking the next leg.

```bash
ROOT=/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-endpoint-abba-8936aac-c59aaad-20260723T093923Z

env -i PATH="$PATH" HOME=/home/steve USER=steve LOGNAME=steve SHELL=/bin/bash \
  bash experiments/laguna-s-2.1-xpu-b70/tools/run_w1_n128_crossover_leg.sh \
  control "$ROOT/01-A1-control"

env -i PATH="$PATH" HOME=/home/steve USER=steve LOGNAME=steve SHELL=/bin/bash \
  bash experiments/laguna-s-2.1-xpu-b70/tools/run_w1_n128_crossover_leg.sh \
  candidate "$ROOT/02-B1-candidate"
```

After B1, run the frozen analyzer in phase mode using only A1 and B1, writing
`phase1-analysis.json`, `phase1-analysis.md`, and
`phase1-analysis.stdout` at the campaign root. Continue only if its atomic
phase seal is valid and every preregistered phase gate passes. Then run B2 and
A2 in that order with the same sanitized environment and cooling rule.

```bash
/home/steve/.venvs/deepseek-v4-xpu/bin/python \
  experiments/laguna-s-2.1-xpu-b70/tools/analyze_w1_n128_crossover.py \
  --a1 "$ROOT/01-A1-control" \
  --b1 "$ROOT/02-B1-candidate" \
  --out "$ROOT/phase1-analysis.json" \
  --markdown-out "$ROOT/phase1-analysis.md" \
  >"$ROOT/phase1-analysis.stdout"

env -i PATH="$PATH" HOME=/home/steve USER=steve LOGNAME=steve SHELL=/bin/bash \
  bash experiments/laguna-s-2.1-xpu-b70/tools/run_w1_n128_crossover_leg.sh \
  candidate "$ROOT/03-B2-candidate"

env -i PATH="$PATH" HOME=/home/steve USER=steve LOGNAME=steve SHELL=/bin/bash \
  bash experiments/laguna-s-2.1-xpu-b70/tools/run_w1_n128_crossover_leg.sh \
  control "$ROOT/04-A2-control"
```

After A2, produce the frozen all-leg teacher comparison and cross-leg
comparison reports, then run the full analyzer with the exact four leg paths
and fixed output paths:

```bash
TEACHER=/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json
PYTHON=/home/steve/.venvs/deepseek-v4-xpu/bin/python
COMPARE=experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py
ANALYZE=experiments/laguna-s-2.1-xpu-b70/tools/analyze_w1_n128_crossover.py

"$PYTHON" "$COMPARE" \
  --teacher "$TEACHER" \
  --candidate "$ROOT/01-A1-control/bench.json" \
  --candidate "$ROOT/02-B1-candidate/bench.json" \
  --candidate "$ROOT/03-B2-candidate/bench.json" \
  --candidate "$ROOT/04-A2-control/bench.json" \
  --out "$ROOT/all-vs-canonical-teacher.json"

"$PYTHON" "$COMPARE" \
  --teacher "$ROOT/01-A1-control/bench.json" \
  --candidate "$ROOT/02-B1-candidate/bench.json" \
  --candidate "$ROOT/03-B2-candidate/bench.json" \
  --candidate "$ROOT/04-A2-control/bench.json" \
  --out "$ROOT/cross-leg-exactness.json"

"$PYTHON" "$ANALYZE" \
  --a1 "$ROOT/01-A1-control" \
  --b1 "$ROOT/02-B1-candidate" \
  --b2 "$ROOT/03-B2-candidate" \
  --a2 "$ROOT/04-A2-control" \
  --all-vs-teacher "$ROOT/all-vs-canonical-teacher.json" \
  --cross-leg "$ROOT/cross-leg-exactness.json" \
  --out "$ROOT/full-analysis.json" \
  --markdown-out "$ROOT/full-analysis.md" \
  >"$ROOT/full-analysis.stdout"
```

A LocalMaxxing submission is allowed only if:

- the full analysis seal has `valid: true`;
- the full result has `eligible: true`;
- all 13 complete token arrays in every leg equal the canonical greedy
  teacher bitwise;
- all freshness, request-accounting, canary, identity, causal, pairwise, and
  reproducibility gates pass; and
- the lower candidate throughput strictly exceeds both the lower control and
  the approved record floor.

Only the lower of B1 and B2 may be submitted. There is no fifth run.
