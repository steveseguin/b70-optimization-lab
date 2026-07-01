# Qwen3.6 Spec Trace Summary

## Trace: `/tmp/qwen36-perfectdraft-k4-spec-trace-20260611a.jsonl`

- rows `5`, requests `2`, drafts `20`, accepted `17`, rejected `3`, accept rate `85.00%`
- full accept rows `4` (`80.00%`), full reject rows `0` (`0.00%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `3`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-909b40a6706bbeb2-0-ab131f9c` | 16 | 13 | 3 | 81.25% | 3 |
| `cmpl-8334a38c7287e725-0-9ccae4e0` | 4 | 4 | 0 | 100.00% | 1 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `perfectdraft_k4` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
