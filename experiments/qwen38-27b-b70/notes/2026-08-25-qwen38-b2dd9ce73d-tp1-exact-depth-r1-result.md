# Qwen3.8 b2dd TP1 graph exact-depth result

Date: 2026-08-25. Status: **PASS; six exact TP1 cells measured**.

The frozen b2dd/1e90 zero-overlay image ran Qwen3.8 27B AutoRound W4A16 on
GPU 0 at TP1, MTP0, F16 KV, and `FULL_AND_PIECEWISE` graph mode. One server
measured six exact flat-token inputs with 128 output tokens each:

| Active context | Decode tok/s |
|---:|---:|
| 2,048 | 30.09574673632959 |
| 4,096 | 29.76690784678723 |
| 8,192 | 29.277761929165937 |
| 16,384 | 28.4202492985839 |
| 24,576 | 27.657572566220896 |
| 32,768 | 26.988772332153104 |

Every request proved its frozen fixture and prompt-token hashes,
`usage.prompt_tokens == D`, cache zero, 128 returned token IDs, a length
finish, and the conventional first-100-event/99-interval rate. PIECEWISE and
FULL graph capture markers passed. The same server then passed seven exact
quality cases, eight repeats, the long-context case, all 24 baseline
comparisons, and all 16 cache-zero observations. Cleanup and the unchanged
clean-main gate passed.

Depth zero remains **missing**: its exact fixture is empty, and configured
capacity is not an active-context measurement. The six rates are a distinct
exact-context series. They do not overwrite or lower the protected b2dd
short-workload graph result near `30.31 tok/s`, and no speed floor was used as
a correctness gate.

The terminal run root is
`/home/steve/qwen38-current-main-runs/tp1-exact-depth-b2dd9ce73d-20260825-r1/01-exact-depths`.
Its stage receipt SHA-256 is
`1b79688d384259fa0697c5510cb7903e15d01330923a4c8bc97f09e586907ee6`.
The tracked summary is
[`2026-08-25-qwen38-b2dd9ce73d-tp1-exact-depth-r1-result.json`](../data/2026-08-25-qwen38-b2dd9ce73d-tp1-exact-depth-r1-result.json).
