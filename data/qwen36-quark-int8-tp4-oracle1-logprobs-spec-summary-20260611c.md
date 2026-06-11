# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-quark-int8-tp4-oracle1-logprobs-spec-20260611c.jsonl`

- rows `14`, requests `2`, drafts `14`, accepted `14`, rejected `0`, accept rate `100.00%`
- full accept rows `14` (`100.00%`), full reject rows `0` (`0.00%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `7`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-acf5b461d68d6be8-0-8a3f9970` | 7 | 7 | 0 | 100.00% | 7 |
| `cmpl-9b1806a7f867b71e-0-9d03641c` | 7 | 7 | 0 | 100.00% | 7 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
