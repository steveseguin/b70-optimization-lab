# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-nomambaspec-paired-20260615g7-spec-trace.jsonl`

- rows `4`, requests `2`, drafts `4`, accepted `2`, rejected `2`, accept rate `50.00%`
- full accept rows `2` (`50.00%`), full reject rows `2` (`50.00%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `1`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-b5993198d5c98610-0-a5eee754` | 2 | 1 | 1 | 50.00% | 1 |
| `cmpl-9a26e7b6c9fd7504-0-8ef1c32a` | 2 | 1 | 1 | 50.00% | 1 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
