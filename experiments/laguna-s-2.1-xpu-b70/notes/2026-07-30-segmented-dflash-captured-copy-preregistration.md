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
