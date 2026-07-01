# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle1-pos-trained-tp2-20260618a-spec-trace.jsonl`

- rows `649`, requests `6`, drafts `1947`, accepted `115`, rejected `1832`, accept rate `5.91%`
- full accept rows `7` (`1.08%`), full reject rows `559` (`86.13%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `2`
- repeated scheduled rows `47`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-9f76cd7c9247fb09-0-9ef846a5` | 378 | 1 | 377 | 0.26% | 0 |
| `cmpl-b786a3e1561a9ddc-0-900d1b2f` | 348 | 11 | 337 | 3.16% | 1 |
| `cmpl-b1c3304bc2a902cb-0-b43d65e8` | 345 | 12 | 333 | 3.48% | 1 |
| `cmpl-b4657c9f0a6ac738-0-ad092770` | 336 | 16 | 320 | 4.76% | 0 |
| `cmpl-92d56e7d9b6bdc05-0-a704aae4` | 279 | 35 | 244 | 12.54% | 1 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
