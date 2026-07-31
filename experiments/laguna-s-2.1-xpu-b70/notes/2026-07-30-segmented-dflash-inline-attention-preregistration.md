# Segmented DFlash inline attention

Date: 2026-07-30 America/Toronto

Status: **preregistered before implementation or device execution.**

## Evidence and hypothesis

The exact draft-attention-subgraph result measures 120.806633089 historical
and 119.598566758 conventional tok/s. It clears the requested historical
threshold but remains 0.401433242 tok/s (0.3356%) below 120 under current
99-interval accounting.

That result replays 20 outer draft graphs, six nested attention graphs, and
thirteen unchanged eager all-reduces per speculative cycle. The graph-safe FA2
binary has now captured and replayed all six DFlash attention bodies through a
400-token smoke and a cold 13-prompt exact score.

Recording those six bodies directly into their surrounding outer segments
would remove six nested replays and merge the adjacent outer segments:

```text
current draft: 20 outer graphs / 19 boundaries (6 attention + 13 collective)
candidate:     14 outer graphs / 13 boundaries (13 collective)
```

The target remains 146/145. Arithmetic, attention kernels, output buffers,
and every collective remain unchanged.

The older target-inline experiment was 12/13 exact and showed no attributable
endpoint win. It remains closed. This is a distinct drafter-only treatment:
the DFlash path now has persistent context-KV workspace and has independently
proved its six attention bodies graph-recordable. That distinction is a reason
to run one fail-closed smoke, not evidence that the candidate is correct.

## Sealed treatment

Add default-off
`VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS=1`, valid only with segmented
DFlash and mutually exclusive with nested DFlash attention subgraphs. It:

- applies only to the drafter wrapper;
- leaves target persistent metadata and 146/145 topology unchanged;
- leaves all thirteen draft collectives eager and ordered;
- requires exactly 14 draft graphs / 13 eager boundaries on all ranks;
- uses the same caller-owned attention outputs and graph-safe FA2 binaries;
- leaves selector-off and the approved 20/19 record path unchanged; and
- does not enable the rejected target-inline or whole-drafter graph paths.

No model, quantization, BF16 KV semantic, attention algorithm, sampling rule,
prompt, cache policy, or scoring-window change is allowed.

## Gates and stop rules

1. Focused tests must prove nested/inline exclusion, in-open-segment execution,
   drafter-only wiring, and exact 14/13 expectations.
2. Preserve and inspect the patch before device execution.
3. Run one non-scored two-request 400-token smoke. Require exact q1 prefixes,
   cache-zero, normal decaying acceptance, target 146/145 and draft 14/13 on
   every rank, clean teardown, and post-idle pass.
4. Any token mismatch, topology drift, capture/static error, device/collective
   failure, worker leak, or idle failure closes the route. No retry or recovery
   ladder follows.
5. Only a passed smoke authorizes one cold 13-prompt score. The first valid
   result stands. Promotion requires 13/13 exactness and an improvement over
   119.598566758 conventional tok/s; 120 conventional remains the objective.

This note makes no correctness or performance claim for the candidate.

## Offline implementation

- vLLM base:
  `e63b413ea1bbeb8a367ec390e097c478bd84b7ed`;
- candidate:
  `34b43849fc7c8ff8633f223469cc2a0d525c256e`;
- worktree:
  `/home/steve/src/laguna-vllm-dflash-inline-attention-20260730`;
- source-delta bundle:
  `patches/laguna-s-2.1-xpu-b70/vllm-laguna-dflash-inline-attention-34b43849f-20260730.bundle`;
- bundle SHA-256:
  `fa2caf605a53b8c84aacf281d5e90e3eac2b989aa62f8fcd330d2d69fe821451`;
- focused wrapper/breakable-graph gate:
  `51 passed, 11 skipped`; and
- Ruff, Python compilation, Bash syntax, bundle verification, and whitespace
  checks: pass.

The harness carries inline attention as its explicit 32nd argument, records
and verifies the live flag, rejects nested+inline use, and changes the audited
draft expectation to 14/13 only when inline mode is selected.

These are offline results only. The next authorized device action is one
non-scored 400-token smoke.

## Non-scored live smoke: substantive gates pass, stale analyzer rejects

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-inline-attention-smoke-20260731T034640Z
```

The sole authorized smoke ran both 400-token requests. The smoke program
validates each response, cache counter, draft-cycle count, and decaying
accepted-per-position curve before it inspects graph logs. It reached the
graph-log check, proving those request gates passed. The server log records
target 146/145 and the preregistered draft 14/13 for capture and replay on all
four ranks, with no runtime/device/collective error. Cleanup reports
`original_status=1 stop_status=0 worker_status=0 idle_status=0`.

The nonzero original status came only from a stale smoke-analyzer constant:
it still searched for draft 20/19, so it reported zero matching draft rows
despite the actual required 14/13 rows being present 4/4 for both capture and
replay. The service is not rerun. The analyzer and scored topology checker now
take explicit expected draft graph/break counts from the harness; their CPU
gate passes, including 14/13.

All substantive preregistered smoke gates passed in the one device attempt.
The next authorized action is one cold 13-prompt score with the repaired
analyzer plumbing and the same candidate identity.
