# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-quark-int8-tp4-oracle1-nobonus-windowtrace-nograph-20260612b-spec-trace.jsonl`

- rows `16`, requests `2`, drafts `16`, accepted `7`, rejected `9`, accept rate `43.75%`
- full accept rows `7` (`43.75%`), full reject rows `9` (`56.25%`)
- suppressed bonus rows `7` (`43.75%`)
- max full-accept streak `1`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-b91ff19ab73b4067-0-b9b868c3` | 9 | 4 | 5 | 44.44% | 1 |
| `cmpl-ad89ee64ab2ec346-0-99927445` | 7 | 3 | 4 | 42.86% | 1 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `window` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
