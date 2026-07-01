# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-metadata-spec-20260611f.jsonl`

- rows `4`, requests `2`, drafts `4`, accepted `2`, rejected `2`, accept rate `50.00%`
- full accept rows `2` (`50.00%`), full reject rows `2` (`50.00%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `1`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-9756faeb830d5269-0-9a98622f` | 2 | 1 | 1 | 50.00% | 1 |
| `cmpl-bbd73cef12100532-0-8227d06d` | 2 | 1 | 1 | 50.00% | 1 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
