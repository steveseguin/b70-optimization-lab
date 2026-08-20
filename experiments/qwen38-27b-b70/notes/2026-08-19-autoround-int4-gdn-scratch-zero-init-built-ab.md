# Zero-init GDN scratch: built, A/B-measured, graph-validated on the 15 GiB host

Date: 2026-08-19
Status: fix built and op-level validated here; strict server A/B remains
measuring-host work

The collaborator's zero-init patch
(`patches/vllm-xpu-kernels-qwen38-gdn-scratch-zero-init-20260818.patch`,
kernel commit 0ab8205) was filed unbuilt because the measuring host lacked
disk. This host rebuilt it incrementally (ninja, JOBS=1, IntelLLVM 2025.3.3,
BMG-G31 AOT) under a `systemd-run` user scope (MemoryMax=13G). Peak swap use
during the whole build was 768 KiB; the oneGDN TU peaks the earlier full
build saw did not recur for this single-TU increment.

## Artifacts

- fixed `_xpu_C.abi3.so` SHA256
  `3d3a8bde37761303f1d995b989ce21a78092c0aeb3cf5b33c5adc094bf437d3f`,
  staged at `/home/steve/staged-xpu-zero-init-20260819/` (binary provenance
  only; rebuild from the patch for promotion)
- `libgdn_attn_kernels_xe_2.so` relinked **bit-identical** to the pinned
  manifest hash `c194e28d…` — only host-side scratch allocation changed
- pinned binaries backed up at `/home/steve/pinned-xpu-backup-2dd55f38/`

## A/B at exact MTP5 TP2 shapes (no model, direct op calls)

Script `scripts/gdn-spec-decode-scratch-bench.py`; data
`data/2026-08-19-gdn-scratch-ab-{pinned,fixed}.json`. One request, 6
verifier rows, qkvz 8192, ba 48, conv [5120,4], 300 timed iters +
100-call bursts.

| lane | burst us/call (pinned) | burst us/call (fixed) |
|---|---|---|
| record (`PERSISTENT_SCRATCH=0`) | 42.87 | 43.43 |
| persistent (`=1`) | 34.08 | 34.22 |

Net fix effect on the record configuration: **8.8–9.2 µs/call →
0.42–0.44 ms/step** across the 48 GDN layers, i.e. **≈ +1.5% ≈ +1.5 tok/s**
against the 101.922 record (projects ≈103.4, not 105 alone). This is the
real-op measurement behind the earlier allocator-loop estimate
(0.93 ms/step Python-level upper bound).

Zero-init is performance-neutral versus the pinned persistent path
(34.22 vs 34.08 µs/call): one memset, off the hot path, exactly as
0ab8205 notes.

## Functional gates passed here

- established prefix-parity gate (`scripts/check-gdn-native-spec-prefix.py`,
  fp16/fp32 state, Qwen3.8 TP2 shapes, `--persistent-scratch
  --require-bit-exact`): all 4 cases bit-exact at **both** MTP5 (spec-len 5,
  `data/2026-08-19-gdn-prefix-parity-fixed-mtp5.json`) and the
  production-failing MTP4 shape (spec-len 4,
  `data/2026-08-19-gdn-prefix-parity-fixed-mtp4.json`), including
  varied-accepted-count restarts and padding poison checks.
- graph regime: 200 XPU-graph replays of the fixed persistent lane are
  bit-exact against eager (`GRAPH_OK`) — the production lane runs this op
  inside captured graphs.

## Sensitivity caveat (important)

The same parity gate run against the **pinned** (uninitialized-scratch)
build at the MTP4 shape also passes bit-exact
(`data/2026-08-19-gdn-prefix-parity-pinned-mtp4.json`). In a fresh process
the caching allocator returns predictable memory, so no op-level synthetic
gate here can observe the history-dependent read — the production 24/25
failure needed long-lived allocator residue from real serving. Conclusion:
these gates prove the fix **preserves the contract and performance**, but
the bug-removal proof is inseparable from the measuring host's strict-25
rerun with `PERSISTENT_SCRATCH=1`.

## What remains (measuring host)

1. Rebuild from the patch (or smoke with the staged .so), run the strict-25
   with `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1`: expect ≈103–104 and 25/25
   determinism. A pass also unblocks serial-exact at MTP4/5, which
   hard-requires `=1`.
2. Then the rerank K=2 screen for the remaining ≈1.5–4.5 tok/s to 105.
