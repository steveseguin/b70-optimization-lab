# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-graph-currentref-20260615a-spec.jsonl`

- rows `30`, requests `2`, drafts `30`, accepted `29`, rejected `1`, accept rate `96.67%`
- full accept rows `29` (`96.67%`), full reject rows `1` (`3.33%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `20`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a` | 20 | 20 | 0 | 100.00% | 20 |
| `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000001-0-b2c2291b` | 10 | 9 | 1 | 90.00% | 9 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
