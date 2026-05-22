# MiniMax M2.7 gmem095 Quality Guardrail - 2026-05-21

## Goal

After the `compile_sizes=[1,2]` probe showed a tiny warm throughput movement with `--gpu-memory-utilization 0.95`, isolate whether the movement came from the memory-utilization knob or the extra compile-size specialization.

## Result Summary

`--gpu-memory-utilization 0.95` by itself is not quality-safe under the raw145 exact-token canary:

- Promoted default-memory config: passed exact raw145 n64 canary.
- Promoted config plus `--gpu-memory-utilization 0.95`: failed exact raw145 n64 canary.
- `compile_sizes=[1,2]` plus `--gpu-memory-utilization 0.95`: passed exact raw145 n64 canary again.

The failed gmem095-only output was coherent and non-degenerate, but it started by echoing the prompt text. That is still output drift, so the result is not acceptable for promotion.

## Throughput Control

Warm p512/n1536 control using promoted compile sizes `[1]` plus `--gpu-memory-utilization 0.95`:

- Mean decode throughput: `92.81513428257155` tok/s
- Mean total throughput: `123.75351237676206` tok/s
- Decode stdev: `0.020496334057190233` tok/s
- Per-repeat decode tok/s: `92.83526222124725`, `92.78806014923823`, `92.81160624755772`, `92.825608512243`

This speed is not promotable because the matching quality canary failed.

## Quality Checks

Promoted default-memory repeat:

- Expected combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Observed combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Passed: `true`

Promoted `[1]` plus `--gpu-memory-utilization 0.95`:

- Expected combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Observed combined token SHA256: `6481f1ad4ce52b09aa2e951b8b744235191ba03eeadb73b6277a93511da9db90`
- Passed: `false`
- Degenerate/control/NUL checks: passed, but exact token hash failed.

`compile_sizes=[1,2]` plus `--gpu-memory-utilization 0.95`, fresh cache repeat:

- Expected combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Observed combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Passed: `true`

## Decision

Do not promote `--gpu-memory-utilization 0.95` by itself. It gives a small warm throughput bump but fails the exact-token canary.

Do not promote `compile_sizes=[1,2] + --gpu-memory-utilization 0.95` either. It is quality-clean in repeated canary tests, but the speed gain is tiny, the default-memory startup path failed, and fresh compilation adds significant startup cost.

No LocalMaxxing submission was made. This is a guardrail/learning result, not a shareable speed achievement.

## Artifacts

- gmem095 warm control JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/promoted-gmem095-control-warm-20260521T040658Z/minimax-promoted-gmem095-control-warm-vllm-random-text-p512n1536.json`
- gmem095 quality-fail JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/promoted-gmem095-control-quality-20260521T041214Z/minimax-promoted-gmem095-control-raw145-n64.json`
- promoted default quality-pass JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/promoted-default-quality-repeat-20260521T041553Z/minimax-promoted-default-raw145-n64.json`
- compile `[1,2]` gmem095 quality-pass repeat JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/compile-sizes-1-2-gmem095-quality-repeat-20260521T041849Z/minimax-compile-sizes-1-2-gmem095-repeat-raw145-n64.json`
- Summary data: `data/minimax-m27-gmem095-quality-guardrail-20260521.json`
