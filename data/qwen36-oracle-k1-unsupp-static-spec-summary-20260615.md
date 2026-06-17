# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-oracle-k1-unsupp-static-20260615-spec.jsonl`

- rows `23`, requests `2`, drafts `23`, accepted `23`, rejected `0`, accept rate `100.00%`
- full accept rows `23` (`100.00%`), full reject rows `0` (`0.00%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `16`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-oraclek1unsupp-000001-0-b27267a4` | 16 | 16 | 0 | 100.00% | 16 |
| `cmpl-oraclek1unsupp-000000-0-920f34dd` | 7 | 7 | 0 | 100.00% | 7 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `candidate` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `True`
- note: Artifacts store request ids, but no trace request ids matched. Check whether the trace and artifact came from the same run.

