# Qwen3.8 official FP8 TP2 p64 scheduler factorial R8 result

Status: **complete negative diagnostic; retain 256-token synchronous control**.

All three preregistered arms completed on independent fresh servers. Every arm
returned 64 complete 128-token-ID responses, used zero cached prompt tokens,
passed cross-base output isolation, exited the harness successfully, and left
a clean container/process/port state.

| Arm | Batched-token budget | Async | Aggregate tok/s | Delta vs control | TTFT p50 / p95 |
| --- | ---: | :---: | ---: | ---: | ---: |
| qualified control | 256 | no | **695.792088** | — | 889.84 / 1,744.03 ms |
| `mbt4096` | 4,096 | no | 676.783304 | -2.73% | 1,485.72 / 2,036.05 ms |
| `async256` | 256 | yes | 658.475126 | -5.36% | 1,579.19 / 2,432.68 ms |
| `async4096` | 4,096 | yes | 666.478647 | -4.21% | 1,645.70 / 2,196.25 ms |

No arm reached the frozen `730.581692 tok/s` confirmation threshold. A larger
prompt-admission budget increased rather than reduced c64 TTFT, and async
scheduling regressed both tested budgets. No arm advances to confirmation or
changes the package. Keep `max_num_batched_tokens=256` with synchronous
scheduling for this exact target-only/MTP0, size-one-graph FP8 TP2 service.

Evidence:
[4,096/sync](../data/qwen38-fp8-tp2-http-p64-scheduler-factorial-20260826-r8-mbt4096-attempt1/),
[256/async](../data/qwen38-fp8-tp2-http-p64-scheduler-factorial-20260826-r8-async256-attempt1/),
[4,096/async](../data/qwen38-fp8-tp2-http-p64-scheduler-factorial-20260826-r8-async4096-attempt1/),
[preregistration](2026-08-26-qwen38-fp8-tp2-http-p64-scheduler-factorial-r8-preregistration.md).
