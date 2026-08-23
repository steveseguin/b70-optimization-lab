# D1/D2 v2 infrastructure probe: valid traces, validator stage mismatch

Date: 2026-08-23. Raw root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-chunkdiag-probe-20260823-d1d2-v2`.

## Outcome

The server, smoke, one-row dose benchmark, and quality battery completed with
runner exit code 0. The outer diagnostic driver stopped with code 15 because
the fail-closed D1/D2 validator expected a `fallback_pre_conv` D2 stage. No D7
or D4 mechanism arm was launched.

D1 is structurally valid: 4,134 records; allocate/free coverage for groups
0, 1, and 2; twelve prefill metadata records for the 1,024 + 220 token chunks;
consumed slots 20, 26, and 32; zero live-slot collisions.

D2 is also structurally valid, but the native lane emits a different call-site
name than preregistered. Four rank-0/layer-0 records were written:

- `pre_native`, computed tokens 0, `has_initial_state=[false]`, slot 20;
- `post_native_prefill_mirror`, computed tokens 0, flag false;
- `pre_native`, computed tokens 1024, `has_initial_state=[true]`, slot 20;
- `post_native_prefill_mirror`, computed tokens 1024, flag true.

Source inspection confirms `pre_native` is emitted immediately before the
native `torch.ops._xpu_C.gdn_attention` call that consumes
`attn_metadata.has_initial_state`. The fallback-stage expectation was wrong;
the evidence itself was not missing or malformed.

## Cache and speed safety

All four AOT archives loaded directly from
`/var/tmp/qwen38-chunkdiag-d1d2-v2-cache-20260823`. The log has no source-guard
recompile or AOT save. The protected recovered cache was not used as a runtime
cache. Probe throughput is diagnostic-only and is not a promoted speed result.

The probe output manifest SHA-256 is
`8ce2ed4646f6fa33563c20619d382e5d13b3a7b60e609b03230e968c608b55b3`.
D1 SHA-256 is
`8189947f705a8e6a439eb9d925a6431104ae1afb06d2c6110a8acdb446868400`;
D2 SHA-256 is
`46a7ca6aa5da946e8c94d5cfb62d9d96061d42b85816d4d365a4bbecf05a53e7`.

Per the re-registration, changing the validator creates implementation v2b
and requires one fresh infrastructure probe. The mechanism cap remains two
arms only after that probe passes.
