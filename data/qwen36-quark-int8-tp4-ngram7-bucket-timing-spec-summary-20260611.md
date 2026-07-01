# Qwen3.6 Spec Trace Summary

## Trace: `/tmp/qwen36-ngram7-bucket-timing-spec-trace-20260611t.jsonl`

- rows `10`, requests `2`, drafts `70`, accepted `38`, rejected `32`, accept rate `54.29%`
- full accept rows `3` (`30.00%`), full reject rows `1` (`10.00%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `2`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-8645f1153d20f1c5-0-906af458` | 63 | 35 | 28 | 55.56% | 2 |
| `cmpl-8441165602a1f67c-0-9e35665e` | 7 | 3 | 4 | 42.86% | 0 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-quark-int8-tp4-ngram7-bucket-timing-repetitive-p512o96-20260611` | `repetitive` | 96.29 | [96] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `1`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
