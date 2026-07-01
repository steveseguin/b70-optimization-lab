# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle1-corpus-trained-singlestate-commitbefore-nopreempt-tp2-20260618a-spec-trace.jsonl`

- rows `46`, requests `2`, drafts `46`, accepted `34`, rejected `12`, accept rate `73.91%`
- full accept rows `34` (`73.91%`), full reject rows `12` (`26.09%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `22`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-990d78ecba4c219d-0-872276af` | 31 | 25 | 6 | 80.65% | 22 |
| `cmpl-bf38c68e2edeb6ad-0-86a299b6` | 15 | 9 | 6 | 60.00% | 6 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-eagle1-corpus-trained-singlestate-commitbefore-nopreempt-naturalchat16-tp2-20260618a-measure` | `natural-chat` | 0.52 | [16] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `1`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
