# MiniMax M2.7 AutoRound INT4 — four-B70 candidate package

This package organizes the lab's older speed-focused 2K-context MiniMax lane.
It uses four B70s, vLLM/XPU TP4, the retained vLLM and llm-scaler patch
snapshots, and strict token-hash quality gates. The promoted four-run mean was
`89.314195 output tok/s`.

> **Status: expert candidate.** The recipe includes system setup, model
> download, source restore/build, runtime checks, quality gates, and benchmark
> scripts, but it has not been replayed on a current clean host.

The [reproduction guide](../../repro/minimax-m27-b70-89tps-20260520/README.md)
is authoritative.

## Who built what

**neural.download lab — integrated:** B70/XPU integration, MiniMax MoE
work-sharing and custom-op work, graph/runtime fixes, strict quality gates,
benchmarking, and this package. The promoted change measured `+0.4343%` over
the preceding promoted result.

**Lasimeri — acknowledged:** published the AutoRound W4A16 checkpoint used by
this lane. It is credited as the model dependency; this packet does not invent
a separate quantization speed or quality uplift.

## Important identity limitation

The historical run recorded the model repository but not its snapshot revision
or a complete payload manifest. The download helper now pins immutable revision
`1afac074ecf7c3c4504c68b83d127506f8a7e5a4` for future replays. That is a
reconstruction pin, not proof that the old local payload was byte-identical.

## Exact route

On a dedicated Ubuntu 24.04 host with four idle B70s:

```bash
cd repro/minimax-m27-b70-89tps-20260520
sudo bash scripts/00-install-system-deps.sh
sudo reboot
```

After reboot, from the same directory:

```bash
bash scripts/01-download-model.sh
bash scripts/02-build-stack.sh
bash scripts/03-verify-runtime.sh
bash scripts/04-run-quality-gate.sh
bash scripts/05-run-benchmark.sh
bash scripts/06-summarize-result.sh /mnt/fast-ai/bench-results/minimax-m27-b70-89tps
```

Do not use a cold compile result for comparison. The expected warm band is
`87.5–90.0 output tok/s`; the quality gate must pass first. This exact lane is
a benchmark runner, not yet a persistent OpenAI-compatible service package.

## Certification gaps

The route needs a current clean-host replay, a complete model manifest, tested
beginner recovery, a precise platform compatibility boundary, and a service
wrapper for this exact identity.
