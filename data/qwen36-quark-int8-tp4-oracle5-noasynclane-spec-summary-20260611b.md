# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-quark-int8-tp4-oracle5-noasynclane-spec-20260611b.jsonl`

- rows `12`, requests `2`, drafts `52`, accepted `52`, rejected `0`, accept rate `100.00%`
- full accept rows `12` (`100.00%`), full reject rows `0` (`0.00%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `6`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-a72274b03be59916-0-877d56fc` | 26 | 26 | 0 | 100.00% | 6 |
| `cmpl-94b7e14e5fb2f3a1-0-b8688e55` | 26 | 26 | 0 | 100.00% | 6 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
