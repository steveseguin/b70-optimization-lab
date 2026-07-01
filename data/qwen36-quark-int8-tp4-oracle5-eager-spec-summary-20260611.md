# Qwen3.6 Spec Trace Summary

## Trace: `/tmp/qwen36-oracle5-eager-spec-trace-20260611b.jsonl`

- rows `6`, requests `2`, drafts `30`, accepted `22`, rejected `8`, accept rate `73.33%`
- full accept rows `4` (`66.67%`), full reject rows `0` (`0.00%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `2`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-8e97cb3bfbebd136-0-adfa6b1b` | 15 | 11 | 4 | 73.33% | 2 |
| `cmpl-80ddf384ef322ae2-0-ae8fd7e4` | 15 | 11 | 4 | 73.33% | 2 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `qwen36-quark-int8-tp4-oracle5-eager-completions-20260611` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
