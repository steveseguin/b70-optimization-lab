# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-quark-int8-tp4-oracle1-nobonus-cachefilter-nograph-20260612c-spec-trace.jsonl`

- rows `6`, requests `2`, drafts `6`, accepted `4`, rejected `2`, accept rate `66.67%`
- full accept rows `4` (`66.67%`), full reject rows `2` (`33.33%`)
- suppressed bonus rows `4` (`66.67%`)
- max full-accept streak `2`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-ba8c478f4f2900cd-0-b3ac4dd6` | 3 | 2 | 1 | 66.67% | 2 |
| `cmpl-934a595531882a8f-0-bc7342d5` | 3 | 2 | 1 | 66.67% | 2 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `cachefilter` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
