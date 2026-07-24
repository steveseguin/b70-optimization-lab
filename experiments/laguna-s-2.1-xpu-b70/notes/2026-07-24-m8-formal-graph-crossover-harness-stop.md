# Laguna M8 formal graph crossover: harness stop after A1

Date: 2026-07-24 America/Toronto

Status: **INCOMPLETE / INELIGIBLE**. This root is not performance evidence and
must not be used for a record or LocalMaxxing submission.

## What happened

The preregistered one-shot controller completed A1 eager, including all 13
fresh prompts, canonical comparison, shutdown, and the full post-stop idle
interval. A1 itself passed:

- canonical q1 token arrays: 13/13 exact;
- `cached_tokens=0`: 13/13;
- long-then-next: pass;
- 863-token rollover: 1/1 exact; and
- shutdown, residual-worker, and idle cleanup: pass.

Before B1 could create a run directory or start a service, its clean-tree
preflight stopped with:

```text
Laguna formal M8 crossover leg: main worktree is dirty
```

The only dirty path was:

```text
experiments/laguna-s-2.1-xpu-b70/tools/__pycache__/
  preflight_laguna_m8_gather_sharded_operational.cpython-312.pyc
```

The A1 leg's pre-service idle helper imported the operational preflight module
without `PYTHONDONTWRITEBYTECODE=1`. This created the bytecode file after A1's
initial clean-tree check. B1's identical check correctly failed closed.

No B1 request, graph capture, phase-1 comparison, B2, or A2 occurred. A1 timing
is an unpaired incomplete-campaign timing and is explicitly ineligible.

## Sealed root

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-formal-graph-crossover-d0960da7e-0ce373a31-20260724T215010Z
```

The campaign and A1 directories are mode `0500`; evidence files are mode
`0400`. The root will not be resumed or modified.

Key SHA256:

```text
56492b6ac53fdafc730a3ff9124efa215d05863a3c1d521149385260ab4edb10  controller-identity.txt
593bb79c12e1d93e9fc696401e53689132d1599030d159f3f64a448f0806c874  A1-eager/bench.json
a38e6535582d7e3c2cc19f1b45893fc843bb1e8e505de7d50c4347ed9fb2baee  A1-eager/exactness-vs-q1.json
e3b1bb9a2a4d8cfd0ba5554c6be27d7acb03d98a5375b24f2862d5dbe31964c7  B1.controller.stderr
1ba9e60bb1f16ee57a01346eab588020551409680f48e4dd3956934c0e82f834  A1-eager/cleanup-status.txt
```

## Fix and retry boundary

Both the controller and leg runner now export
`PYTHONDONTWRITEBYTECODE=1` before any Python subprocess. This is a harness-only
change: it does not alter the model, runtime, kernels, treatment, prompts,
measurement, quality gates, performance gates, order, or stopping rule.

The failed root remains sealed. Any retry requires a new committed tool hash,
a new preregistered root, all clean worktrees, and a complete fresh
A1/B1/B2/A2 campaign under the original gates.
