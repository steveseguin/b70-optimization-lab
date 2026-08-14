# Muse-Glimmer-30B handoff

Status: **closed and banked 2026-08-13**.

Use [README.md](README.md) for the promoted result and
[`../../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813`](../../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md)
for exact restoration. Do not continue from old `CURRENT.md` experiment prose,
the clean `llama.cpp-muse-glimmer` baseline, or the historically mislabeled
`noprofile` config.

The original BF16/lossless objective missed. The accepted successor is Q8/WOQ,
target-verified, and no-training. It passed the two canonical century runs and
the frozen cold-suite gate, but prose/full-natural throughput and universal
token exactness remain outside the claim. No LocalMaxxing receipt exists.

The source worktree and large local artifacts may remain useful for audit, but
the durable source of truth is now the patch/bundle/evidence in Git. Start the
next model in a clean, separate worktree and experiment directory.
