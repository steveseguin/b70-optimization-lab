# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-quark-int8-tp4-oracle5-noasynclane128-spec-20260611b.jsonl`

- rows `8`, requests `2`, drafts `40`, accepted `31`, rejected `9`, accept rate `77.50%`
- full accept rows `6` (`75.00%`), full reject rows `1` (`12.50%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `4`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-b237a19acddd5cdc-0-a4a208c9` | 25 | 20 | 5 | 80.00% | 4 |
| `cmpl-8379d606f1b85d39-0-a3af3a70` | 15 | 11 | 4 | 73.33% | 2 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
