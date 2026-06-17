# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-oracle1-logprobs-eager-20260615g17-spec-trace.jsonl`

- rows `31`, requests `2`, drafts `31`, accepted `31`, rejected `0`, accept rate `100.00%`
- full accept rows `31` (`100.00%`), full reject rows `0` (`0.00%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `16`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-9e889ab93af9e508-0-bc868c53` | 16 | 16 | 0 | 100.00% | 16 |
| `cmpl-a5dd1236f8cd7ebd-0-ad3b7bd3` | 15 | 15 | 0 | 100.00% | 15 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.

