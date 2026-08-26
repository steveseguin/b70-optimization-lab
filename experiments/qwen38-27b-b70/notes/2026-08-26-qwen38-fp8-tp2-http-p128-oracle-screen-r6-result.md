# Qwen3.8 official FP8 TP2 p128 oracle and capacity screen R6 result

Status: **complete negative diagnostic; do not promote p128**.

The preregistered one-server R6 run completed successfully and generated the
new 128-row compact output oracle. All 128 sequential oracle responses returned
exactly 128 token IDs with zero cached prompt tokens. Every response in the
c1/2/4/8/16/32/64/128 ladder also returned 128 raw token IDs, reported zero
cached prompt tokens, and passed the cross-base output-isolation check. The
harness exited zero and cleanup was clean.

| Active requests | Aggregate tok/s | TTFT p50 | TTFT p95 |
| ---: | ---: | ---: | ---: |
| 1 | 21.622252 | 67.75 ms | 67.75 ms |
| 2 | 41.334090 | 123.37 ms | 174.03 ms |
| 4 | 80.477032 | 228.70 ms | 228.85 ms |
| 8 | 154.215890 | 288.33 ms | 288.79 ms |
| 16 | 280.556667 | 294.27 ms | 437.05 ms |
| 32 | 468.030453 | 485.85 ms | 832.23 ms |
| 64 | **694.134013** | 887.19 ms | 1,744.94 ms |
| 128 | 619.791890 | 1,762.57 ms | 17,748.39 ms |

The c128 result is 10.71% below c64 on the same fresh server and 10.92% below
the qualified p64 control (`695.792088 tok/s`). It misses the frozen
`730.581692 tok/s` confirmation threshold by `110.789802 tok/s`. Consequently,
R6 stops here: no confirmation servers will be run and no p128 rate will replace
the published p64 profile.

This closes `max_num_seqs=128` as a throughput improvement under the otherwise
fixed target-only/MTP0, FP16-KV, 4,096-token-capacity, 256-batched-token service
shape. It does not establish that 64 is globally optimal under different
scheduler limits or kernels.

Evidence: [complete attempt directory](../data/qwen38-fp8-tp2-http-p128-oracle-screen-20260826-r6-attempt1/),
[preregistration](2026-08-26-qwen38-fp8-tp2-http-p128-oracle-screen-r6-preregistration.md).
