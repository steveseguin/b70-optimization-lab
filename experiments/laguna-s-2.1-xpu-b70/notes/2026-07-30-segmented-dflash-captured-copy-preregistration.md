# Segmented DFlash captured boundary copies

Date: 2026-07-30 America/Toronto

Status: **preregistered before implementation or device execution.**

## Evidence and hypothesis

Two independent cold exact segmented-DFlash legs now measure:

| leg | historical tok/s | preferred 99-interval tok/s |
| --- | ---: | ---: |
| first | 119.189370967 | 117.997477257 |
| confirmation | 119.695499867 | 118.498544868 |

Both are 13/13 token-and-text exact, cache-zero, target 146/145, draft 20/19,
and operationally clean. The historical 120 objective is 0.304500133 tok/s
above the confirmation; the preferred objective is 1.501455132 tok/s above
it.

The rejected in-place candidate proved the boundary tensors exist at stable
capture addresses, but correctly failed the wrapper's static-input guard
because the state mutated from thirteen `None` slots before capture to
thirteen bound tensors afterward. That guard must not be weakened.

The incumbent already owns thirteen preallocated `[12,3072]` BF16 outputs.
Each eager collective callback currently submits:

```text
output.copy_(local)
all_reduce(output)
```

The copy can remain arithmetically identical and target the same fixed output
while being recorded at the tail of the preceding compute graph. The eager
boundary then submits only the unchanged all-reduce. Replay order remains:

```text
captured compute + copy -> eager all_reduce -> next captured compute
```

This removes thirteen separate host submissions per speculative cycle without
removing a collective, changing a tensor address, or weakening static-input
validation.

## Sealed treatment

Add one default-off selector:

```text
VLLM_XPU_LAGUNA_DFLASH_CAPTURE_COLLECTIVE_COPIES=1
```

It is valid only with the exact BF16-KV width-12/depth-11 segmented-DFlash
contract. The treatment:

- preserves the original thirteen preallocated, non-aliasing outputs;
- preserves all thirteen eager TP all-reduces and their order;
- records only each existing `output.copy_(local)` in the preceding compute
  segment;
- validates the fixed output signature before the eager reduction;
- keeps six attention operations eager;
- keeps draft topology exactly 20/19 and target topology exactly 146/145; and
- leaves the selector-off call path unchanged.

No weight, quantization, BF16 KV semantic, target width, DFlash depth,
sampling/rejection rule, prompt, cache policy, graph count, collective count,
or scoring window changes.

## Gates and stop rules

1. CPU/static tests must prove selector-off behavior, copy-before-boundary
   ordering, output identity checks, replay accounting, overflow/count
   accounting, and runtime rejection outside the segmented graph contract.
2. Inspect the actual source and preserved patch after editing.
3. Run exactly one non-scored two-request, 400-token smoke. Require q1-prefix
   exactness, cache-zero, more than 33 cycles per request, normal acceptance,
   146/145 and 20/19 on every rank, clean teardown, and post-idle pass.
4. Any token mismatch, topology drift, static-identity failure, capture error,
   collective hang, worker leak, or idle failure closes the route. Do not
   retry, probe again, reset, reload/unbind the driver, issue FLR, or delete
   shared-memory objects.
5. Only after the smoke passes may one cold 13-prompt score run. Report the
   first valid result, including both accounting conventions. Do not warm,
   omit prompts, retry, move capture outside the score, or cherry-pick starts.

This note makes no correctness or throughput claim for the treatment.

## Offline implementation

- vLLM base:
  `4f5e7a63cbd0d0bb409207e079421d0d5532d197`;
- branch:
  `experiment/laguna-dflash-captured-copies-20260730`;
- candidate commit:
  `cbbaff469`;
- worktree:
  `/home/steve/src/laguna-vllm-dflash-captured-copies-20260730`;
- preserved patch:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-capture-segmented-DFlash-collective-copies.patch`;
- patch SHA-256:
  `ba142d3eb8a406e7f6003d961f4464d9a35600aacd850a772a8267e34a6473a6`;
- focused vLLM gate: `47 passed`;
- segmented smoke parser gate: `6 passed`; and
- Ruff, Python compilation, Bash syntax, and relevant whitespace checks:
  pass.

The implementation uses the original thirteen preallocated outputs. With the
selector on, `copy_(local)` executes while the preceding outer graph segment
is still recording. Ending that segment materializes the copy before the eager
callback invokes only the checked all-reduce. The wrapper's static signature
therefore remains unchanged before and after capture. Selector-off execution
still calls the original copy-plus-reduce callback.

The measurement harness records and verifies this as its explicit 30th
argument, rejects use without segmented DFlash, and rejects combining it with
the closed in-place treatment.

These are offline results only. The next authorized device action is exactly
one non-scored 400-token smoke.

## Non-scored live smoke: pass

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-captured-copy-smoke-20260731T025411Z
```

The one authorized smoke passed:

- both 400-token responses matched their canonical q1 prefixes;
- both reported `cached_tokens=0`;
- request-local draft-cycle counts were 105 and 62;
- accepted-per-position curves were non-flat and decayed from 83 to 6 and
  from 54 to 15;
- draft 20/19 and target 146/145 capture/replay appeared on all four ranks;
- no OOM, device-lost, static-identity, or collective error occurred; and
- formal service stop, worker/listener cleanup, and post-idle interval passed.

This diagnostic emitted no throughput score. The preregistered next action is
one cold 13-prompt scored leg with the same candidate identity.

## Cold scored leg: exact, operationally clean, no throughput win

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-captured-copy-scored-20260731T030057Z
```

The first and only authorized cold score passed every validity gate:

- 13/13 token-and-text exact against the canonical q1 teacher;
- all prompt-cache counters zero;
- draft 20/19 and target 146/145 on all four ranks;
- graceful worker shutdown and strict post-idle pass; and
- `original_status=0 stop_status=0 worker_status=0 idle_status=0`.

Measured throughput:

| leg | historical tok/s | preferred 99-interval tok/s |
| --- | ---: | ---: |
| captured copies | 119.192374497 | 118.000450752 |
| segmented first | 119.189370967 | 117.997477257 |
| segmented confirmation | 119.695499867 | 118.498544868 |

The treatment reproduced the first segmented result almost exactly and was
about 0.42% below the independent confirmation. Removing thirteen standalone
copy submissions therefore has no measurable throughput benefit under the
cold-suite noise floor. The implementation is correct and preserved for
reference, but this route is **closed as a performance optimization**. Do not
retry it or combine it speculatively with another treatment.
