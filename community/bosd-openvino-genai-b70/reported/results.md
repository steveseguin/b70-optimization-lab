# Raw results

All on one Arc Pro B70 (`GPU.1` / `level_zero:1`), Fedora 44, kernel
`7.2.10-200.fc44`, host Level-Zero `1.33.1`. Single-stream, greedy decode.

## OpenVINO GenAI 2026.4.1 — Qwen2.5-7B-Instruct-int4-ov (`~/ov-bench.py both`)

```
=== OV INT4 no-spec (device GPU.1) ===
[tech] tput=114.0 tok/s  ttft=18ms  tpot=8.8ms  ntok=256
[code] tput=112.5 tok/s  ttft=84ms  tpot=8.9ms  ntok=256

=== OV INT4 + spec(draft 1.5B, k=5) (device GPU.1) ===
[tech] tput=98.6  tok/s  ttft=19ms  tpot=10.1ms ntok=256
[code] tput=128.2 tok/s  ttft=88ms  tpot=7.8ms  ntok=256
```

- Draft = `OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov`, `num_assistant_tokens=5`.
- Smoke (1.5B int4, "Explain what a GPU kernel is…"): coherent, ~0.3 s.

## llama.cpp-SYCL — Qwen2.5-7B-Instruct-Q4_K_M.gguf (4.36 GiB)

Stale build `5aba5364d` (2026-06-01), `~/llama.cpp/build-sycl`:

```
| test  |            t/s |
| pp512 | 1082.84 ± 3.94 |
| tg128 |   13.16 ± 0.06 |     # +flash-attn: 13.78 ± 0.07 — no change
```

Fresh build `970b51c` (2026-10-22), `-DGGML_SYCL_DNN=OFF`, `-fa 1`:

```
| test  |             t/s |
| pp512 | 3528.17 ± 28.30 |
| tg256 |   98.58 ±  0.29 |
```

(A short `-n 128 -r 3` run on the fresh build gave `72.5 ± 46.6` — unstable
cold/short; the `-n 256 -r 6` steady-state number `98.58 ± 0.29` is the one to
quote.)

## Summary

| Engine / build | Decode tok/s | pp512 |
| --- | --- | --- |
| OV GenAI INT4 no-spec | ~113 | — |
| OV GenAI INT4 + 1.5B spec | 98.6 / 128.2 | — |
| llama.cpp-SYCL fresh (2026-10-22) | 98.6 | 3528 |
| llama.cpp-SYCL stale (2026-06-01) | 13.2 | 1083 |

OpenVINO GenAI leads a **current** llama.cpp-SYCL by ~15% single-stream; both
near the B70 memory-bandwidth roofline (~107 tok/s for 4.2 GB INT4/token).
