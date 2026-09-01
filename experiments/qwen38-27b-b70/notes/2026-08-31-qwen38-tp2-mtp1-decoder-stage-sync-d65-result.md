# Qwen3.8 TP2/MTP1 decoder-sync D65 startup confirmation

Date: 2026-08-31

D65 passed the frozen zero-request startup-only qualification on the two local
B70s. It used immutable image
`sha256:a1454ebe9adc227b0dc5eb867c2b9a58ca12cc2594a41c4f070118d6f04cc13c`,
loaded the direct-verified local AutoRound INT4 target, enabled MTP depth 1,
disabled projection repair, and imported the patched vLLM source from
`/workspace/vllm`.

Both ranks completed both full profile/model-forward passes. The log contains
exactly 2,080 decoder `begin` receipts and 2,080 matching `pass` receipts:

`65 layers × 8 boundaries × 2 ranks × 2 profile passes = 2,080`

Each of the nine dummy-sampler stages produced exactly four pass receipts (two
ranks times two profile passes). The first and second HTTP health checks passed,
the API reached readiness, teardown was clean, and the timestamp-bounded kernel
log contains no Xe fault/reset/timeout, device loss, OOM, filesystem, or I/O
fault event. No inference request was served.

This confirms the mechanism only: enforcing device completion at decoder
boundaries prevents the D61-D63 TP2/MTP1 startup failure. It does not qualify
decode, TTFT, acceptance, output parity, determinism, or promotion. The next arm
must scope synchronization to vLLM profile forwards so normal request execution
has no barrier cost, then pass startup before strict output/performance testing.

Raw evidence:
`/mnt/fast-ai/bench-results/qwen38-tp2-mtp1-decoder-stage-sync-20260831-d65/`.
