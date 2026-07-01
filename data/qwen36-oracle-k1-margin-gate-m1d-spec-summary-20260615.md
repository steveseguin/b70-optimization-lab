# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-margin-gate-m1d-20260615-spec.jsonl`

- rows `23`, requests `2`, drafts `23`, accepted `21`, rejected `2`, accept rate `91.30%`
- full accept rows `21` (`91.30%`), full reject rows `2` (`8.70%`)
- suppressed bonus rows `1` (`4.35%`)
- max full-accept streak `12`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-margin-gate-m1d-20260615-000000-0-9d0ee333` | 13 | 12 | 1 | 92.31% | 12 |
| `cmpl-qwen36-oracle-k1-margin-gate-m1d-20260615-000001-0-87e0b248` | 10 | 9 | 1 | 90.00% | 9 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
