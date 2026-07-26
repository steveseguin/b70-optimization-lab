# Laguna S 2.1 resume point

Last updated: 2026-07-26 America/Toronto

## Status

The requested objective is complete.

- measured primary result: **`102.97143559613157 tok/s`**;
- objective: `102 tok/s`;
- margin: `+0.97143559613157 tok/s`;
- LocalMaxxing: `cms2ccv2d00lps201rej94pjy` (`APPROVED`);
- lane state: record sealed, no active benchmark, service, or worker.

Do not resume from the former 94.920 record, the obsolete recovery block, or
the abandoned tree/selector ideas. They are historical evidence, not current
work.

## Record identity

| Field | Value |
| --- | --- |
| Target | `poolside/Laguna-S-2.1-INT4` at `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb` |
| Draft | `poolside/Laguna-S-2.1-DFlash-INT4` at `5e07c246915c86dc6920fead03d019989224f2ba` |
| vLLM | `e596ef1543466ae1a05e5bb8091f58872e2b18ba` |
| XPU kernels | `6f9dd3c3a7b1b677a992ca4f431a968408f9c816` |
| Layout | TP4+EP4, one active generation |
| Target verifier | exact width 12 |
| DFlash | depth 11, greedy draft, standard rejection |
| Graph | audited Breakable PIECEWISE capture size 12, 146 graphs / 145 eager breaks per rank |
| KV | BF16 |
| Treatment | 31 runtime E4M3FN W8A16 DFlash dense-projection conversions per rank plus the exact auxiliary workspace |
| Selector | `VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=1` |

The intended separate FP8 draft-LM-head path exists in source, but its expected
runtime preparation message is absent from the record log. Do not attribute
the measured gain to that head. The evidence-backed treatment is limited to
the 31 logged draft projections and auxiliary workspace.

## Formal command and artifact

```bash
experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_mwide_measurement_leg.sh \
  candidate B2 RUN_DIR 12 11 1 0 0 0 0 0 0 1 1
```

Sealed run:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-width12-dflash-fp8-e596ef154-20260726T214259Z
```

Promoted records:

- exact source bundles and combined patches:
  `patches/laguna-s-2.1-xpu-b70/`;
- packet:
  `data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json`;
- note:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-width12-dflash-fp8-w8a16-record.md`;
- submission queue:
  `data/localmaxxing-laguna-s-2.1-int4-b70-width12-dflash-fp8-102.971tok-20260726.queue.json`;
- submission response:
  `data/localmaxxing-responses/laguna-s-2.1-int4-b70-width12-dflash-fp8-102.971tok-20260726.response.json`.

## Gates that passed

- fixed realistic suite, 13 unique prompts;
- each prompt invoked exactly once;
- no warmup generation and no retry;
- first valid score is the reported score;
- 13/13 token IDs and text bitwise exact vs the canonical q1 teacher;
- `cached_tokens=0` on all 13 requests;
- long-then-next 2/2 and rollover 1/1 exact;
- target capture and replay witnessed on all four ranks;
- 146/145 topology exact on every rank;
- 73-second prestart and poststop idle intervals;
- clean service, worker, and port teardown;
- target model, target LM head, verifier, sampling policy, and target KV
  semantics unchanged.

## What went wrong earlier

The old recovery wrapper resolved a nonexistent scratch-local probe path.
Several summaries therefore reported `0/4` even though the probe never entered
Python. Driver reload, FLR, and shared-memory cleanup conclusions made from
those summaries were unfounded. Later corrected full-model runs proved the live
TP4/XCCL path healthy, so the old recovery block is closed.

The submission helper also pointed speed records at the retired
`/api/benchmarks` route and accepted an HTTP 200 HTML shell as success. It now
uses `/api/speed-tests`, validates the exact projected request through the
authenticated server dry-run, and accepts only HTTP 201 JSON containing a
nonempty ID and status.

## Rules for any future optimization

1. Preregister the selector, treatment, control, primary metric, and stop
   conditions before running a score-bearing leg.
2. Preserve the fixed suite and canonical teacher. Never change the target,
   omit slow prompts, cherry-pick starts, move setup outside the scored window,
   warm the service, or substitute a more favorable metric.
3. Require one active generation, `cached_tokens=0`, one invocation per prompt,
   no prefix/history/response reuse, and target verification of every accepted
   draft token.
4. Diff the complete run identity before interpreting speed. Require exact
   source commits, model revisions, binaries, flags, graph capture sizes, and
   146/145 topology.
5. Inspect the source file after editing it. Inspect per-rank logs and explicit
   execution markers before trusting summary counters.
6. Treat a failed or missing probe as unknown. Never escalate privileged
   recovery unless the probe proves that it executed and classifies the
   failure boundary.
7. Keep every negative patch/result in the experiment ledger, commit focused
   changes, and leave all experimental selectors default-off.
8. Report the first valid result honestly, whether it wins or loses.

No next action is required for the 102 tok/s goal. Any further benchmark or
hardware action needs a new objective and a new preregistration.
