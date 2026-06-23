# 20260623T0900 Parallel / Cache Follow-Ups

## Goal

Start from the validated optimized-SYCL + `FLASH_ATTN=off` base and test
single-session server settings:

- `--parallel 1`, to avoid four llama-server slots for a one-session target;
- `THREADS=16`, after thread-count smokes nudged after-TTFT decode up;
- `--cache-ram 0`, after logs showed prompt-cache update stalls with one slot.

## Results

| Label | Change | Canary | p512/o512 tok/s after TTFT | Wall tok/s | Decision |
| --- | --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu0-syclopt0-faoff-parallel1-20260623T0800` | `--parallel 1`, default threads | 128/128 | `41.9229` | `35.8948` | smoke win; default deep run invalidated by script edit mid-run |
| `gemma4-q8-gpu1-syclopt0-faoff-parallel1-poll100-20260623T0815` | `--parallel 1`, `POLL=100` | 128/128 | `41.8095` | `35.4492` | no win |
| `gemma4-q8-gpu2-syclopt0-faoff-parallel1-t4-20260623T0815` | `--parallel 1`, `THREADS=4` | 128/128 | `41.9974` | `36.0963` | smoke win over prior approved |
| `gemma4-q8-gpu3-syclopt0-faoff-parallel1-t16-20260623T0815` | `--parallel 1`, `THREADS=16` | 128/128 | `42.0394` | `35.3365` | deep-validated below |
| `gemma4-q8-gpu3-syclopt0-faoff-parallel1-t16-deep-20260623T0830` | `--parallel 1`, `THREADS=16` | 384/384 | `41.9213` | `36.1123` | validated, but superseded by cache0 |
| `gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-20260623T0900` | `--parallel 1 --cache-ram 0`, `THREADS=16` | 128/128 | `42.0300` | `35.6997` | smoke win |
| `gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-deep-20260623T0915` | `--parallel 1 --cache-ram 0`, `THREADS=16` | 384/384 | `42.1539` | `36.4063` | **current promoted best** |
| `gemma4-q8-gpu0-syclopt0-faoff-parallel1-cache0-poll100-20260623T0915` | cache0 + `POLL=100` | 128/128 | `41.9924` | `36.1634` | no win |
| `gemma4-q8-gpu1-syclopt0-faoff-parallel1-cache0-poll25-20260623T0915` | cache0 + `POLL=25` | 128/128 | `41.8549` | `35.7819` | no win |
| `gemma4-q8-gpu3-syclopt0-faoff-parallel1-cache0-ub128-20260623T0915` | cache0 + `UBATCH_SIZE=128` | 128/128 | `41.9971` | `35.8185` | no win |

## 32K Viability

`gemma4-q8-gpu1-syclopt0-faoff-parallel1-ctx32768-smoke-20260623T0845` loaded
with Q8 weights, f16 KV, `CTX_SIZE=32768`, and `--parallel 1`, then passed
`64/64` chat canary rows. The short p512/o512 smoke measured `41.9509 tok/s`
after TTFT, but it is not a record because the canary depth was intentionally
lighter and the purpose was context viability.

## Decision

Promote `gemma4-q8-gpu2-syclopt0-faoff-parallel1-cache0-deep-20260623T0915` as
the new Q8 B70 single-GPU best and submit a LocalMaxxing update.
