# Qwen3.6 Spec Trace Summary

## Trace: `/tmp/qwen36-ngram5-bucket-timing-spec-trace-20260611s.jsonl`

- rows `19`, requests `2`, drafts `92`, accepted `38`, rejected `54`, accept rate `41.30%`
- full accept rows `4` (`21.05%`), full reject rows `6` (`31.58%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `2`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-aaa7b2732820a0ee-0-9c62e9a1` | 87 | 35 | 52 | 40.23% | 2 |
| `cmpl-bafc1b19fd9e47ef-0-8db6cdc6` | 5 | 3 | 2 | 60.00% | 0 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-quark-int8-tp4-ngram5-bucket-timing-repetitive-p512o128-20260611` | `repetitive` | 84.67 | [128] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `1`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
