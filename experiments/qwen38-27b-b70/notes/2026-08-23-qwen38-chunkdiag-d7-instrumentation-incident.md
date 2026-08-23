# D7 instrumentation incident: evidence green, sealed cache mutated

Date: 2026-08-23. Raw root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-chunkdiag-d7-20260823-d1d2-a`.

## Valid evidence

- All seven long-KV rows completed with 512 tokens and zero cached prompt
  tokens.
- The post-dose needle remained exact:
  `B70_QWEN36_NEEDLE_20260609`; quality `pass_all=true`.
- D1 wrote 15,741 JSONL records. SHA-256:
  `4077ab4616f93a3d68b459b8f4f4c1d308410651627141853c822d3283275e97`.
- Benchmark SHA-256:
  `f05ef3dfdd90bb3bbd2e46e4ae2ea951ddb0cf592356f2a9d8b48f8b97868248`.
- Quality SHA-256:
  `7856a34e712a5a2a1e59f1b8b255bbbfa1a11e91a885b7de6ef6628438bcaf5b`.

## Instrumentation failure

The dedicated D2 call-site file was never created even though D1 recorded
chunked-prefill metadata. D2 therefore has no evidence from this arm. It must
not be called dead or confirmed from D7.

## Cache-protection failure

Changing the Python source invalidated the AOT source guard. vLLM recompiled
the `dc9285...` outer and wrote two model files into the protected sealed
cache. The runner had `VALIDATION_REQUIRE_COMPILE_CACHE_UNCHANGED=1`, but the
postflight was incorrectly conditional on the separate sealed-gate flag,
which this report-only driver disables. That logic is now fixed to enforce the
unchanged-cache contract independently, and the driver treats runner codes
greater than one as infrastructure failures even if quality output exists.

Only these two files differ from the sealed manifest:

| Path suffix | Expected size / SHA-256 | D7 size / SHA-256 |
|---|---|---|
| `dc9285.../rank_0_0/model` | `12691224` / `e1672ae9af223baf5c283760c82872003ec45a6206ecc2f159a627b7c578a7ed` | `12685489` / `36ff2f260afe6dbc638b684e595fb6128b6f265305e2df5a3ed3777e5642cb5e` |
| `dc9285.../rank_1_0/model` | `12691215` / `d5a564bd9eb28f2e131435728745c050221f111cfd31a706b524554df8da5d64` | `12685489` / `f62e873da0467ad216923fbd2fe988e7d425fb5575418a000acfde025dc303e3` |

The mutated complete cache was preserved at
`/var/tmp/qwen38-cache-recovery.2m1KYi/torch_compile_cache` before any repair.
The protected cache must be restored to its manifest exactly before another
campaign run. D4 is stopped until that recovery succeeds; no result from D7
is a promoted speed capture.

## Recovery outcome

Two clean-source recovery boots were made against copies, never against the
visible underlying protected tree: first at a private ext4 path, then through
a bind mount at the exact historical path. Both boots were quality-green, but
PyTorch's regenerated AOT archives were not byte-identical to the 2026-08-20
archives. The historical two hashes could not be reproduced and were not
silently redefined.

After unmounting, the underlying D7-instrumented pair was backed up and
replaced with the clean-source, exact-path pair that had just served the
quality-green recovery arm:

- rank 0: `f306010249d47e52e867211649a633d1b25f3274001180d90e5d4cd47e8a3c1e`;
- rank 1: `c7dc51e7180864814d7dc0df59c949f9d811d3505def48f1bd36a2d380b5d484`.

The recovered clean tree has 3,795 entries, 395,835,376 file bytes, and tree
SHA-256 `41467a0d835657d50e6fa701c5b011cf6228a68f77109953486032f56b9095ad`.
Its manifest is
`/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820/recovered-clean-output-manifest-20260823.json`
(file SHA-256
`98b2ac9397021c21c2124d1ee1327b9fab6c14aee4145eb2fffd0a195c193dcf`).
It is functional recovery evidence, **not** the original sealed identity.

All cache variants, both recovery-arm roots, and both model-pair backups were
copied content-identically (3,254 files, 449,245,240 bytes; NTFS mode bits
differ) to
`/mnt/usb-models/llm-runtime/vllm-cache/qwen38-chunkdiag-recovery-20260823`.
The target-side canonical manifest is
`/mnt/usb-models/llm-runtime/vllm-cache/qwen38-chunkdiag-recovery-20260823.manifest.json`
(SHA-256
`d354a6b51497402de8e7a31db715940f5251e479b6fe8dd178298706c389a9fc`).

D4 was not run. The preregistered mechanism program is stopped as
instrumentation-invalid: D2 had no D7 records, and the protected cache
contract was broken. D1's D7 trace remains evidence that seven doses recycle
cleanly while quality stays green, but neither D1 nor D2 receives a final
confirmed/dead verdict without a fresh preregistration on an isolated cache.
