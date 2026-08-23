# Ornith 1.5 35B-A3B: final `GET_ROWS` direct bypass

Date: 2026-08-23 EDT

Status: **closed engine-neutral — exact, not shipped**

Ornith's Qwen lineage made the remaining serialized `GET_ROWS` time worth
checking, but a temporary execution counter changed the interpretation of the
profile. Across a forced 127-token generation, generic `GET_ROWS` executed 450
times, including 120 convolution-state and 120 GDN-state calls. Those are
prompt/setup shapes. During one-token decode, the accepted direct concat/state
and in-place GDN state paths each fired `3,810 = 127 × 30` times, so recurrent
state gathers were already fully suppressed. The serialized profiler had
charged deferred queued work to logical recurrent nodes; its family total was
not evidence of recurrent decode launches.

The actual remaining warmed-decode gather was a single adjacent boundary:

```text
result_norm:   F32 [2048,1]
GET_ROWS:      F32 [2048,1]
result_output: Q6_K [2048,248320] MUL_MAT
```

The default-off candidate required the exact names, types, shapes, adjacency,
single consumer, and non-aliasing relationship. Because the source has one row,
the only valid gather index is zero. It passed the original `result_norm` row
directly to the existing Q6_K output-head kernel and skipped both the gather and
its graph node. This differs materially from the old Qwen Q8 output-head
candidate: Ornith's Q6_K kernel already consumes FP32, so this path introduced
no serial activation quantization.

The matcher hit exactly 127 times for 127 generated tokens. Control and
candidate forced transcripts were byte-identical with SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.

The matched engine screen used the same final binary, one B70, the accepted
copy-offload setting, `p0/n128/d0/r7`, and mirrored A/B/B/A ordering:

| Arm | Run averages (tok/s) | Mean |
| --- | --- | ---: |
| control | 133.737208, 133.462892 | 133.600050 |
| candidate | 133.698322, 133.612547 | 133.655435 |

The measured change was **+0.0415%**. Removing one launch/token did not clear
the engine promotion threshold, so no serving test was warranted. No result is
extrapolated from the diagnostic serialized timings.

The incremental candidate is preserved at
`../patches/llamacpp-ornith15-final-getrows-direct-neutral-20260823.patch`.
Raw engine, exactness, and launch-audit evidence is under `../data/`. After the
screen, the source diff and the server, benchmark, CLI, and SYCL library were
restored byte-for-byte to the accepted package hashes recorded in the summary.
