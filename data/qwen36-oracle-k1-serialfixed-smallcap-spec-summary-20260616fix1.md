# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-spec.jsonl`

- rows `32`, requests `2`, drafts `32`, accepted `30`, rejected `2`, accept rate `93.75%`
- full accept rows `30` (`93.75%`), full reject rows `2` (`6.25%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `16`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000001-0-9f62fab5` | 16 | 16 | 0 | 100.00% | 16 |
| `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650` | 16 | 14 | 2 | 87.50% | 14 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.

