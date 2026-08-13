# Level Zero lossless memory compression: neutral

Date: 2026-08-13

## Decision

Keep the implementation default-off as a negative hardware screen.  The B70
driver accepts the lossless compression hint and canonical output is preserved,
but verifier round cost does not improve.

No drafter training or weight change was performed.

## Implementation and capability

The installed Level Zero driver advertises
`ZE_extension_memory_compression_hints` v1.0.  Source commit `3bfd7a275`
adds `GGML_SYCL_MEMORY_COMPRESSION=1`, which chains
`ZE_MEMORY_COMPRESSION_HINTS_EXT_FLAG_COMPRESSED` into the existing direct
Level Zero device allocator.  The flag is off by default; arithmetic and bytes
are unchanged.

## Exact A/B

The candidate/control/candidate sweep used the retained TP4 BF16 target,
BF16 DFlash n15 p0.15, parallel host submission, primitive/binding/conversion
caches, and the canonical three 256-token requests.

| arm | prose | code | JSON | mean tok/s | mean normalized round ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| compression on A | 48.119 | 72.883 | 84.962 | 68.655 | 62.150 |
| compression off | 48.339 | 70.377 | 84.701 | 67.806 | 62.127 |
| compression on B | 48.077 | 72.928 | 85.342 | 68.782 | 62.064 |

The apparent raw-throughput difference comes from DFlash accepting 199 code
tokens in both candidate arms versus 197 in control.  Normalizing each class
by its exact round count (`256 - accepted`) removes that proposal variation:
all arms are within 0.09 ms in mean round cost.  All final hashes are canonical.

Raw result:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/l0-memory-compression-ab-20260813.jsonl`;
- SHA-256 `997a79710e915e2051748798d546b89f50de082a807ab929770ec80942386979`.

Production was restored without reboot and passed the full cache-zero
code/vision health gate in
`data/muse-health-20260813-l0-memory-compression-restore.json`.

## Cached-allocation follow-up

Source commit `9274fc5e7` separately adds the default-off
`GGML_SYCL_MEMORY_CACHED=1` screen, which applies Level Zero's lossless
`ZE_DEVICE_MEM_ALLOC_FLAG_BIAS_CACHED` allocation hint.  A cached/control/
cached+compressed comparison was also neutral:

| arm | prose | code | JSON | mean tok/s | mean normalized round ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| cached | 48.156 | 70.436 | 84.751 | 67.781 | 62.178 |
| control | 47.715 | 70.360 | 84.774 | 67.616 | 62.389 |
| cached + compressed | 48.287 | 70.246 | 84.870 | 67.801 | 62.147 |

All three arms had identical proposal counts and canonical final hashes.  The
`0.21--0.24 ms` mean-round differences are below the keep threshold and within
run noise, so both allocation hints remain off by default.

Raw result:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/l0-memory-cache-ab-20260813.jsonl`;
- SHA-256 `03e7d32782954b15b9c21264e46404be01ea3b05517dc86c9daaf149f2031065`.

Production was again restored without reboot and passed the full cache-zero
code/vision health gate in
`data/muse-health-20260813-l0-memory-cache-restore.json`.
