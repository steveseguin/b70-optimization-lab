# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-oracle1-fullbonus-graph-20260615g3-spec-trace.jsonl`

- rows `16`, requests `2`, drafts `16`, accepted `15`, rejected `1`, accept rate `93.75%`
- full accept rows `15` (`93.75%`), full reject rows `1` (`6.25%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `8`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-88d3d0d524cd03d0-0-a153089a` | 9 | 8 | 1 | 88.89% | 8 |
| `cmpl-ac1b34d038cd3a2e-0-984e9884` | 7 | 7 | 0 | 100.00% | 7 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `candidate` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
