# D1/D2 v2b isolated-cache probe: PASS

Date: 2026-08-23. Raw root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-chunkdiag-probe-20260823-d1d2-v2b`.

## Result

The infrastructure gate passes. The one dose row completed 512 tokens with
zero cached prompt tokens; the quality battery and exact long-context needle
passed. Its observed diagnostic throughput was 69.7535 tok/s, but this is a
one-row instrumented probe and is not a promoted speed capture.

The fail-closed validator passed with no errors:

- D1: 4,134 records; groups 0/1/2 allocated and freed; twelve metadata
  records for 1,024 + 220 prompt chunks; consumed slots 20/26/32; zero
  live-slot collisions.
- D2: two `pre_native` records for rank 0 / GDN layer 0; computed-token
  counts 0 then 1024; `has_initial_state=[false]` then `[true]`; state slot 20
  in both chunks.

Evidence SHA-256 values:

- D1: `45791518db34bbe78dbb1ff55618eaba7673ce2992dec097c61a1e9085a16bb2`;
- D2: `5b7355c599d9c3556ef649814d8b8d68667fa82774d101990311bd7ce962b3ac`;
- validator: `1be2aa7d8e77968305dc8fbaaf2ceb52a9ffdc9dd4fccc35d7a0fc366f4d200b`;
- benchmark: `a2d9ee1ec5d8fa84c6c8714436bd4c6cbdcc8f9f8ec58d7bed969204ff2c5a36`;
- quality: `3850ceedcdf201a8a653323a113933f4f169880ec16b29e9309ea9c2e9a4f4de`.

## Cache proof

The first isolated probe normalized mode bits on 58 files copied from NTFS
(0777 to 0664); it changed no file content, size, path, or count. V2b began
from that normalized manifest and its input/output manifests are
byte-identical:

- manifest SHA-256:
  `8ce2ed4646f6fa33563c20619d382e5d13b3a7b60e609b03230e968c608b55b3`;
- 3,795 entries, 395,835,376 file bytes;
- tree SHA-256:
  `846aabb53b0da546de9ff76b8f0acfb827b37d4bf75792d3b9fbe82803b587b2`.

The log contains four AOT direct loads and two outer graph direct loads, with
no recompile/save marker. The protected recovered source cache verifies
unchanged after the probe. D7 and D4 are now authorized in that order with
cache writes forbidden and this exact manifest as input.
