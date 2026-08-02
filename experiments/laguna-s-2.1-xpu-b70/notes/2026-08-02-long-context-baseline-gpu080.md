# Laguna long-context baseline at GPU utilization 0.80

Date: 2026-08-02 America/Toronto

## Result

Laguna-S 2.1 INT4 served and passed the complete intrinsic retrieval gate from
1K through an exact 32,768-token request on four B70 GPUs. All measured prompts
used BF16 KV, prefix caching off, exact input token arrays, 128 generated
tokens, M12/DFlash11, and the protected 146/145 target plus 14/13 draft graph
topology. All three unique 256-token requests immediately after 32K also
passed, so the run found no cross-request contamination.

This is `PASS_BASELINE_ORACLE_NOT_TESTED`, not a q1-exact promotion. The new
long-context target-only oracle still needs to be generated and compared. The
protected short-context result remains unchanged at 125.461973 conventional
tok/s; no record is claimed or submitted here.

The complete baseline is composed from three sealed artifacts because the
guarded full run established 1K/4K before stopping at 8K, then bounded runs
completed 8K and the remaining contexts:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-long-context-mbt8192-gpu080-swap24g-baseline-20260802T182000Z
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-long-context-mbt8192-gpu080-swap24g-8k-probe-20260802T182500Z
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-long-context-mbt8192-gpu080-swap24g-remaining-20260802T183000Z
```

## Context scaling

The 1K row excludes the first-live capture/JIT row. All other groups contain
early, middle, and late fact placement. Values below are medians.

| prompt tokens | prefill tok/s | client TTFT s | decode tok/s | acceptance |
|---:|---:|---:|---:|---:|
| 1,024 | 5,171.878 | 0.202 | 153.604 | 23.56% |
| 4,096 | 7,331.793 | 0.564 | 80.243 | 11.36% |
| 8,192 | 4,129.894 | 1.993 | 46.810 | 2.34% |
| 16,384 | 5,111.214 | 3.228 | 40.414 | 0.86% |
| 24,576 | 5,053.233 | 4.883 | 39.783 | 0.85% |
| 32,640 | 7,345.070 | 4.478 | 39.589 | 0.47% |

The long-context decode decline tracks speculative acceptance rather than a
loss of the target graph identity. Acceptance collapses below one percent from
16K onward, so DFlash performs almost all draft work without accepting tokens.
The long-context decode plateau around 39--40 tok/s is therefore the first
optimization target for draft policy/model behavior, not evidence that the
M12 target decode kernel regressed.

The striking preprocessing defect is instead visible in the post-32K
sentinels: each new 256-token prompt passed retrieval but took about 13 seconds
to first token and only 19.4--19.7 prefill tok/s. The exact Laguna path
intentionally serializes `13 <= M <= 512` one row at a time, while larger
prompts use the wide path. A default-off, pure-prefill-only deterministic
chunk-of-8 treatment is therefore the next source experiment. Decode/verifier
M<=12 and both graph topologies must remain untouched.

## Infrastructure identity and health

GPU memory utilization 0.90 allocated capacity for 224,081 KV tokens but
exhausted the host's original 8 GiB swap. Utilization 0.80 retained between
91,258 and 109,059 KV tokens (2.78--3.33 exact 32K requests) and was sufficient.
The successful long sweep used a temporary, non-persistent 16 GiB swap file in
addition to the system 8 GiB swap, plus an 8 GiB available-RAM guard. Its
minimums were 10,569,440 KiB available RAM and 17,194,160 KiB free swap. No OOM
or XPU error occurred, cleanup was clean, and XPU-SMI level-1 diagnostics
passed all four devices after the run.

The kernel did report three corrected PCIe physical-layer `RxErr` events from
the NVMe endpoint during heavy model/swap I/O. There were no uncorrected AER
bits, the controller remained `live`, and the current AER status was clear.
The installed system lacks `nvme-cli`/`smartctl`, so a controller SMART query
was not available. The temporary swap file should be disabled and removed
after this validation lane rather than retained as a workstation setting.
