# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-quark-int8-tp4-oracle1-nobonus-cachefilter-keepcomputed-nograph-20260612d-spec-trace.jsonl`

- rows `4`, requests `2`, drafts `4`, accepted `2`, rejected `2`, accept rate `50.00%`
- full accept rows `2` (`50.00%`), full reject rows `2` (`50.00%`)
- suppressed bonus rows `2` (`50.00%`)
- max full-accept streak `1`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-957211a127b2ee63-0-b5740812` | 2 | 1 | 1 | 50.00% | 1 |
| `cmpl-b596fa8e2bd3b7c1-0-a8ba98ed` | 2 | 1 | 1 | 50.00% | 1 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `keepcomputed` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.

