# A355: the narrow-view fast path is bit-identical and worth 0.9 ms

Preregistration: `2026-09-12-a355-serial-gdn-views-fast-path-prereg.md`. MTP1 promoted line,
overlay `bbda09ae`, `VLLM_XPU_GDN_SERIAL_SPEC_DECODE_VIEWS=1` (confirmed in the derived server
script and the server process environment).

| arm | M=2 verify step median (ms) | rows |
|---|---|---|
| A344 control | 42.66 | afffd211 x3 |
| A355 views fast path | 41.80 (min 40.01) | afffd211 x3 |

The prediction was near 34 ms; the result is 41.8. The path is exact and slightly faster, so it can
stay on as a default later, but the index_select/index_copy glue was not the second row's cost.
Under full-graph replay the small launches are nearly free; what remains is the work the serial
path does per row: two decode-kernel launches per layer and full-slot state copies between spec
columns. A356-A358 separate those (`2026-09-12-a356-a358-inside-the-serial-gdn-path-prereg.md`).
