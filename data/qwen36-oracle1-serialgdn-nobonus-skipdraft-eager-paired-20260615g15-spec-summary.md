# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-nobonus-skipdraft-eager-paired-20260615g15-spec-trace.jsonl`

- rows `28`, requests `2`, drafts `28`, accepted `26`, rejected `2`, accept rate `92.86%`
- full accept rows `26` (`92.86%`), full reject rows `2` (`7.14%`)
- suppressed bonus rows `26` (`92.86%`)
- max full-accept streak `16`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 16 | 16 | 0 | 100.00% | 16 |
| `cmpl-a10e1749ff57ba54-0-97d8299c` | 12 | 10 | 2 | 83.33% | 8 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.

