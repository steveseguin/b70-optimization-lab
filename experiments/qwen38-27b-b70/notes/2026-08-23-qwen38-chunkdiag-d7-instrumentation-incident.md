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
