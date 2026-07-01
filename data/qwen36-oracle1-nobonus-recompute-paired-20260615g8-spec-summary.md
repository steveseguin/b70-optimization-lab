# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-nobonus-recompute-paired-20260615g8-spec-trace.jsonl`

- rows `14`, requests `2`, drafts `14`, accepted `13`, rejected `1`, accept rate `92.86%`
- full accept rows `13` (`92.86%`), full reject rows `1` (`7.14%`)
- suppressed bonus rows `13` (`92.86%`)
- max full-accept streak `8`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 9 | 8 | 1 | 88.89% | 8 |
| `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` | 5 | 5 | 0 | 100.00% | 5 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
