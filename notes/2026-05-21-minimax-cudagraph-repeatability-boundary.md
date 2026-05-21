# 2026-05-21 MiniMax Cudagraph Repeatability Boundary

## Summary

The fast 4x B70 MiniMax M2.7 AutoRound path is now narrowed to a cudagraph replay repeatability issue.

Normal graph replay is fast and does not show the earlier NUL/control corruption, but it fails exact-repeat checks by n512. Eager mode and graph compile with `cudagraph_mode=NONE` both reproduce the same raw145 n512 output hash exactly. The cost is large: the warm p512/n1536 output rate drops to about 41.70 tok/s when cudagraph replay is disabled.

## Raw145 N512 Boundary

Prompt: raw145 repetitive Greek-token prompt.

| Runtime variant | Exact repeat | Elapsed for 2x512 tokens | Notes |
| --- | --- | ---: | --- |
| graph default | FAIL | 10.594 s | no NUL/control, first repeat hash matches safe path |
| graph async scheduling off | FAIL | 15.350 s | async scheduling is not the cause |
| graph + cudagraph warmups=2 | FAIL | 14.839 s | extra capture warmup is not enough |
| graph + cudagraph copy inputs | FAIL | 15.026 s | input-copy capture is not enough |
| graph + `cudagraph_mode=NONE` | PASS | 30.813 s | exact hash matches eager |
| eager | PASS | 62.008 s | slow correctness anchor |

The shared deterministic raw145 n512 hash for eager and cudagraph-none is:

`faa1113318d1ee669cf204baa22dad501a6b9505a7211d13cf44a716f304e95b`

## Longer Raw145 Checks

- graph raw145 n512: failed `nondeterministic lstrip_text`; 1024 tokens checked, 34 distinct, no NUL/control.
- graph raw145 n1024: failed `nondeterministic lstrip_text`; 2048 tokens checked, 34 distinct, no NUL/control.
- graph raw145 n1536: failed `nondeterministic lstrip_text`; 3072 tokens checked, 41 distinct, no NUL/control.

The failure is not the obvious output corruption seen in rejected custom-collective experiments. It is normal text divergence under greedy repeat.

## Warm Speed Cost Of Safe Capture-Off Path

Warm persistent-engine p512/n1536 with `cudagraph_mode=NONE`:

- Mean output: 41.702862 tok/s
- Mean total: 55.603816 tok/s
- Output stdev: 0.153413 tok/s
- Repeat hashes: all identical

This is quality-clean for token repeatability, but too slow to satisfy the current performance goal.

## Semantic Long Check

Fast graph default was also checked with the three default semantic prompts at n512 and two greedy repeats.

- Exact repeat: FAIL
- Semantic marker regexes: PASS for all prompts/runs
- Generated tokens checked: 2824
- Distinct generated tokens: 580
- NUL/control/degenerate output: none

The semantic markers are intentionally lightweight. They prove the fast graph path did not collapse or emit control garbage, but they do not certify full answer quality. The previews also show that the current semantic harness is too weak for long-answer quality certification because it accepts reasoning-style text that may not fully obey formatting instructions.

## Decision

Do not promote a new fast cudagraph result as quality-certified.

The current honest states are:

1. Fast cudagraph replay: around 93 tok/s warm p512/n1536, semantic-looking output, but exact-repeat unstable at n512+.
2. Cudagraph disabled: around 41.70 tok/s warm p512/n1536, exact-repeat clean.
3. Eager: exact-repeat clean, slower than cudagraph disabled.

For LocalMaxxing and reproducibility docs, keep the accepted 93.443623 tok/s result labeled as a warm speed result, but do not claim it has passed the new long exact-repeat quality gate.

## Next Work

1. Build a stronger persistent-engine quality harness that measures warm speed and long semantic quality in the same process.
2. Compare fast cudagraph replay against cudagraph-none/eager on answer-level semantic canaries, not just hash equality.
3. Add stricter prompt-specific checks for format compliance, for example numbered-list shape and function-only Python output.
4. Inspect the XPU graph replay path and communicator no-op capture path for stale/reused per-token state, especially around input ids, positions, KV metadata, and local argmax/logits shortcuts.
5. If exact-repeat stability remains required for published results, use `cudagraph_mode=NONE` as the strict correctness fallback and treat the performance work as a search for a cudagraph replay fix.
