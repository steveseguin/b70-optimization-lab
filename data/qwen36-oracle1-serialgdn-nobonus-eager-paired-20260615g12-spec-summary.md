# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-nobonus-eager-paired-20260615g12-spec-trace.jsonl`

- rows `28`, requests `2`, drafts `28`, accepted `26`, rejected `2`, accept rate `92.86%`
- full accept rows `26` (`92.86%`), full reject rows `2` (`7.14%`)
- suppressed bonus rows `26` (`92.86%`)
- max full-accept streak `16`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-afa8c098828ad82c-0-b81e5701` | 16 | 16 | 0 | 100.00% | 16 |
| `cmpl-bb269f86687f8609-0-ab507fe3` | 12 | 10 | 2 | 83.33% | 8 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.

