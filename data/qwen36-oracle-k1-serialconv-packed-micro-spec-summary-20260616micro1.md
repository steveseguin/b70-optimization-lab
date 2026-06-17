# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-oracle-k1-serialconv-packed-micro-20260616micro1-spec.jsonl`

- rows `6`, requests `2`, drafts `6`, accepted `4`, rejected `2`, accept rate `66.67%`
- full accept rows `4` (`66.67%`), full reject rows `2` (`33.33%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `3`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-serialconv-packed-micro-20260616micro1-000000-0-aa57a94e` | 4 | 3 | 1 | 75.00% | 3 |
| `cmpl-qwen36-oracle-k1-serialconv-packed-micro-20260616micro1-000001-0-967fc9b9` | 2 | 1 | 1 | 50.00% | 1 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.

