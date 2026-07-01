# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-quark-int8-tp4-oracle1-nobonus-recompute-nograph-20260612f-spec-trace.jsonl`

- rows `20`, requests `2`, drafts `20`, accepted `19`, rejected `1`, accept rate `95.00%`
- full accept rows `19` (`95.00%`), full reject rows `1` (`5.00%`)
- suppressed bonus rows `19` (`95.00%`)
- max full-accept streak `12`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 13 | 12 | 1 | 92.31% | 12 |
| `cmpl-afca347990bfd32e-0-996685b4` | 7 | 7 | 0 | 100.00% | 7 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `recompute` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
