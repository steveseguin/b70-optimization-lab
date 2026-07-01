# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-oracle-k1-smallcap-micro-20260616micro1-spec.jsonl`

- rows `25`, requests `2`, drafts `25`, accepted `23`, rejected `2`, accept rate `92.00%`
- full accept rows `23` (`92.00%`), full reject rows `2` (`8.00%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `13`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-smallcap-micro-20260616micro1-000001-0-a4372f7a` | 13 | 13 | 0 | 100.00% | 13 |
| `cmpl-qwen36-oracle-k1-smallcap-micro-20260616micro1-000000-0-bb7ea2a6` | 12 | 10 | 2 | 83.33% | 10 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
