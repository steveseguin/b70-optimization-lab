# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-spec-jsonl-20260611.jsonl`
- rows: `6`
- malformed rows: `0`
- requests: `3`
- suppressed follow-up mismatches: `1`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | follow-up mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| `chatcmpl-8d175ba4ed1de4c0-a690c281` | 4 | 20 | 14 | 6 | 2 | `long_context_needle (scheduler_prefix)` | 1 | 0 |
| `chatcmpl-9921ca8777ee6db5-a982c57e` | 1 | 5 | 5 | 0 | 1 | `copy_phrase (scheduler_prefix)` | 0 | 0 |
| `chatcmpl-ba141f1fd8db6894-815e0bf2` | 1 | 5 | 0 | 5 | 0 | `json_schema (scheduler_prefix)` | 0 | 0 |

## Suppressed Follow-Up Mismatches

- request `chatcmpl-8d175ba4ed1de4c0-a690c281` line `5` -> `6`:
  suppressed `21` `None` but next verifier token was `15` `None`

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `chatcmpl-8d175ba4ed1de4c0-a690c281` | 3 | 6 | 5 | 0 | -1 | 5 | 5 |
| `chatcmpl-8d175ba4ed1de4c0-a690c281` | 4 | 6 | 0 | 5 | -5 | 1 | 1 |
| `chatcmpl-8d175ba4ed1de4c0-a690c281` | 5 | 6 | 5 | 0 | -1 | 5 | 5 |
| `chatcmpl-8d175ba4ed1de4c0-a690c281` | 6 | 6 | 4 | 1 | -1 | 5 | 5 |
| `chatcmpl-9921ca8777ee6db5-a982c57e` | 1 | 6 | 5 | 0 | -1 | 4 | 4 |
| `chatcmpl-ba141f1fd8db6894-815e0bf2` | 2 | 6 | 0 | 5 | -5 | 1 | 1 |
