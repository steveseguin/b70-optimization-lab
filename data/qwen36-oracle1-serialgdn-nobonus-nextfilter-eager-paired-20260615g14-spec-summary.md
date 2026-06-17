# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-nobonus-nextfilter-eager-paired-20260615g14-spec-trace.jsonl`

- rows `28`, requests `2`, drafts `28`, accepted `26`, rejected `2`, accept rate `92.86%`
- full accept rows `26` (`92.86%`), full reject rows `2` (`7.14%`)
- suppressed bonus rows `26` (`92.86%`)
- max full-accept streak `16`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-951d349832e28038-0-ade216a9` | 16 | 16 | 0 | 100.00% | 16 |
| `cmpl-82f4bbd0bf52b7dd-0-b417a974` | 12 | 10 | 2 | 83.33% | 8 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.

