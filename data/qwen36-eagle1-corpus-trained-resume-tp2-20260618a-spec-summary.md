# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle1-corpus-trained-resume-tp2-20260618a-spec-trace.jsonl`

- rows `58`, requests `2`, drafts `58`, accepted `22`, rejected `36`, accept rate `37.93%`
- full accept rows `22` (`37.93%`), full reject rows `36` (`62.07%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `1`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-87fb5d2360441935-0-b705c7b6` | 38 | 13 | 25 | 34.21% | 1 |
| `cmpl-9f74cfa052d60087-0-89ddd18d` | 20 | 9 | 11 | 45.00% | 1 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-eagle1-corpus-trained-resume-naturalchat-tp2-20260618a-measure` | `natural-chat` | 6.44 | [64] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `1`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
