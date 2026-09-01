# Qwen3.8 TP2/MTP1 decoder-sync D64 cardinality false-fail

Date: 2026-08-31

D64 corrected the runtime import identity and completed both of vLLM's
profile/model-forward passes without a device loss. The exact patched source
was active: startup logs contain 2,080 decoder `begin` and 2,080 matching
`pass` receipts. The full accounting is exact:

`65 layers × 8 boundaries × 2 ranks × 2 profile passes = 2,080`

Every one of the 1,040 unique action/layer/type/stage keys appears four times
(two ranks times two passes). Both full-attention and linear-attention/GDN
layers completed, all sampler stages completed, the server reported available
KV cache, and the API reached application readiness. The captured kernel delta
contains no Xe fault/reset/timeout/device-loss event.

The runner nevertheless exited 1 because its older sampler receipt gate
expected one profile pass per rank (`2` receipts per stage). vLLM actually ran
two complete passes per rank, so each stage correctly appeared `4` times. The
literal run remains a cardinality false-fail and did not reach its second
health check. It is not retroactively labeled passed and cannot authorize a
performance run.

The result is strong mechanism evidence: explicit ordering at every decoder
boundary prevents the D61-D63 startup fault. D65 repeats the exact startup-only
arm with only the expected sampler invocation count corrected from one to two
per rank. No other receipt or health rule is relaxed.

Raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-tp2-mtp1-decoder-stage-sync-20260831-d64/`.
