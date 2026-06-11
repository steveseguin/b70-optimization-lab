# Qwen3.6 Spec Trace Summary

## Trace: `/tmp/qwen36-oracle1-short-graph-spec-trace-20260611a.jsonl`

- rows `15`, requests `2`, drafts `15`, accepted `14`, rejected `1`, accept rate `93.33%`
- full accept rows `14` (`93.33%`), full reject rows `1` (`6.67%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `7`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-96c535d8fe063261-0-9b4f19dd` | 8 | 7 | 1 | 87.50% | 7 |
| `cmpl-a606b4e303f78310-0-842ceef3` | 7 | 7 | 0 | 100.00% | 7 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `qwen36-quark-int8-tp4-oracle1-short-graph-completions-20260611` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
