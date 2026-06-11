# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-jsonl-20260611.jsonl`
- rows: `4`
- malformed rows: `0`
- requests: `3`
- suppressed follow-up mismatches: `1`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | follow-up mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| `chatcmpl-8f59ad636cb2ec08-965c37d8` | 2 | 10 | 5 | 5 | 1 | `` | 1 |
| `chatcmpl-9cb6cf3f172c65ec-91333159` | 1 | 5 | 5 | 0 | 1 | `` | 0 |
| `chatcmpl-976518b6f388f186-afb5dbd2` | 1 | 5 | 0 | 5 | 0 | `` | 0 |

## Suppressed Follow-Up Mismatches

- request `chatcmpl-8f59ad636cb2ec08-965c37d8` line `3` -> `4`:
  suppressed `83098` `_NEED` but next verifier token was `0` `!`
