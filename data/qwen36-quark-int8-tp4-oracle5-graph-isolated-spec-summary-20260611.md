# Qwen3.6 Spec Trace Summary

## Trace: `/tmp/qwen36-oracle5-graph-isolated-spec-trace-20260611a.jsonl`

- rows `8`, requests `2`, drafts `40`, accepted `31`, rejected `9`, accept rate `77.50%`
- full accept rows `6` (`75.00%`), full reject rows `1` (`12.50%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `4`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-8b7d4bf28ef8ebcd-0-b9c6afb2` | 25 | 20 | 5 | 80.00% | 4 |
| `cmpl-92233a55473eedbb-0-bb6d516f` | 15 | 11 | 4 | 73.33% | 2 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `qwen36-quark-int8-tp4-oracle5-graph-isolated-completions-20260611` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.

