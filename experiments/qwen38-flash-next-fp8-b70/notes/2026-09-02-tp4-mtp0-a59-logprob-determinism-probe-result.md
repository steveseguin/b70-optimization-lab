# Qwen3.8 Flash-Next FP8 A59 logprob-resolution probe result

Date: 2026-09-02 14:35--14:55 EDT, boot `95bac684-...` (BIOS 2.4a, Gen4 root
SSD with zero corrected events, GuC 70.72.1)
Status: partial; two first-step repeats captured, then the engine hung on
the third identical request and died; no host freeze

## What happened

The byte-identical A56 server at attempt 59 / port 19731 loaded in
`553.98 s`, captured its graph, and became healthy at 14:47:59. The probe's
first request triggered JIT compilation of the QSA attention kernels
(`_compress_qsa_groups_kernel`, `_store_qsa_rows_kernel`,
`_qsa_mqa_paged_kernel`, `_expand_qsa_indices_kernel`,
`_qsa_sparse_paged_gqa_splitk_kernel`, `_qsa_merge_splitk_kernel`) and
completed in 31.2 s; the second identical request completed in 12.7 s. The
third identical request (256 prompt tokens, `max_tokens=1`, `logprobs=5`)
never produced output: the engine reported `Running: 1 reqs` with zero
throughput from 14:49:25, the EngineCore logged three consecutive 60-second
`shm_broadcast` waits, declared `EngineDeadError` at 14:54:16, and the API
returned HTTP 500. During teardown the kernel logged GPU page faults on
`0000:47:00.0` (repeated, `Fault response: Unsuccessful -EINVAL`) and
`0000:27:00.0` (`-ENOENT`) at 14:54:40, `FaultLevel 4`, faulted address
`0x0000c001ffa67000`. The supervisor recorded the failure, the host wrapper
reported "PLE-only postflight was not clean" (exit 70) and restored swap and
ASPM; all four B70s enumerate afterwards and the root SSD counters stayed
at zero.

## Two findings

1. **The nondeterminism is already present in prefill and the first decode
   step.** With identical 256-token prompts and `max_tokens=1`, the top-1
   token was the same (` using`, id 1608) but its logprob differed:
   `-1.465927` versus `-1.435201`, a spread of `0.0307` nats; the top-2 and
   top-3 logprobs moved by similar amounts. That is not last-bit
   accumulation jitter; it is a materially different forward pass for the
   same input before any graph-replayed decode step runs. Graph replay may
   add more, but it is not the origin.

2. **The hang class survives the firmware upgrade, contained.** On GuC
   70.44.1 the same server line froze the host at worker initialization
   (A57). On 70.72.1 the hang appeared on the third of three identical
   requests, the host stayed up, the driver reported page faults, and the
   run tore down cleanly. A request that hangs nondeterministically after
   two successes is the behaviour of a race, and a race is also the natural
   explanation for finding 1.

## Suspects, ordered

- the public oneCCL `4ceafd1` build: `twoshots` covers only messages up to
  the 4096-byte LL threshold, so prefill-sized reductions (a 64-token chunk
  is 256 KiB at BF16 hidden 2048) take a different algorithm whose
  reduction order and completion signalling may be racy on PCIe P2P;
- the QSA sparse attention path with split-K and a merge kernel, JIT-compiled
  at the first request, possibly reading a workspace that is still being
  written;
- the PLE-only UVA host placement and its lookup/prefetch ordering;
- chunked prefill at 64 tokens interacting with any of the above.

The full-graph capture is not exonerated but is no longer the primary
suspect for the origin.

## Next

An eager control server (same identity minus the graph) with the same probe
separates graph replay from the rest; a second control that lifts the
`twoshots`/public-oneCCL selection targets the collective. Each is a
~25-minute server cycle. Evidence:
`.../attempt59/{server.log,a59-logprob-determinism.json}`, host wrapper log,
kernel journal at 14:54:40.
