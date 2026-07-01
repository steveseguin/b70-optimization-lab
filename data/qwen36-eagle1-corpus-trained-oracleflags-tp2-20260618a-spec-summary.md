# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle1-corpus-trained-oracleflags-tp2-20260618a-spec-trace.jsonl`

- rows `59`, requests `2`, drafts `59`, accepted `23`, rejected `36`, accept rate `38.98%`
- full accept rows `23` (`38.98%`), full reject rows `36` (`61.02%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `2`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-abe027c9c55937c1-0-911e1c93` | 39 | 14 | 25 | 35.90% | 2 |
| `cmpl-aea9814173db39c7-0-90dd2518` | 20 | 9 | 11 | 45.00% | 1 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-eagle1-corpus-trained-oracleflags-naturalchat-tp2-20260618a-measure` | `natural-chat` | 1.05 | [64] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `1`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
