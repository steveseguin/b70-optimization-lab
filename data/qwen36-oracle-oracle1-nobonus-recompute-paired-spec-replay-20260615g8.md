# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-nobonus-recompute-paired-20260615g8-spec-trace.jsonl`
- rows: `14`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `12`
- suppressed schedule mismatches: `12`
- suppressed accept mismatches: `12`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 9 | 9 | 8 | 1 | 8 | `natural_latency_plan (scheduler_prefix)` | 8 | 8 | 8 | 0 |
| `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` | 5 | 5 | 5 | 0 | 5 | `repetitive_kernel_notes (scheduler_prefix)` | 4 | 4 | 4 | 0 |

## Suppressed Follow-Up Mismatches

- request `cmpl-88255c4cb8154477-0-87ee40e0` line `1` -> `2`:
  suppressed `27044` ` dense`, next scheduled `47193` ` numbered`, next verifier token was `47193` ` numbered`, next emitted `47193` ` numbered`.
- request `cmpl-88255c4cb8154477-0-87ee40e0` line `2` -> `3`:
  suppressed `14246` ` engineering`, next scheduled `8129` ` notes`, next verifier token was `8129` ` notes`, next emitted `8129` ` notes`.
- request `cmpl-88255c4cb8154477-0-87ee40e0` line `3` -> `4`:
  suppressed `13` `.`, next scheduled `24985` ` Focus`, next verifier token was `24985` ` Focus`, next emitted `24985` ` Focus`.
- request `cmpl-88255c4cb8154477-0-87ee40e0` line `4` -> `5`:
  suppressed `383` ` on`, next scheduled `3074` ` single`, next verifier token was `3074` ` single`, next emitted `3074` ` single`.
- request `cmpl-88255c4cb8154477-0-87ee40e0` line `5` -> `6`:
  suppressed `43318` `-request`, next scheduled `16401` ` decode`, next verifier token was `16401` ` decode`, next emitted `16401` ` decode`.
- request `cmpl-88255c4cb8154477-0-87ee40e0` line `6` -> `7`:
  suppressed `4478` ` speed`, next scheduled `11` `,`, next verifier token was `11` `,`, next emitted `11` `,`.
- request `cmpl-88255c4cb8154477-0-87ee40e0` line `7` -> `8`:
  suppressed `4779` ` memory`, next scheduled `33389` ` gates`, next verifier token was `33389` ` gates`, next emitted `33389` ` gates`.
- request `cmpl-88255c4cb8154477-0-87ee40e0` line `8` -> `9`:
  suppressed `11` `,`, next scheduled `321` ` and`, next verifier token was `19087` ` Arc`, next emitted `19087` ` Arc`.
- request `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` line `10` -> `11`:
  suppressed `13` `.`, next scheduled `78503` ` Preserve`, next verifier token was `78503` ` Preserve`, next emitted `78503` ` Preserve`.
- request `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` line `11` -> `12`:
  suppressed `4581` ` exact`, next scheduled `2468` ` output`, next verifier token was `2468` ` output`, next emitted `2468` ` output`.
- request `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` line `12` -> `13`:
  suppressed `1345` ` while`, next scheduled `28043` ` measuring`, next verifier token was `28043` ` measuring`, next emitted `28043` ` measuring`.
- request `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` line `13` -> `14`:
  suppressed `7072` ` multi`, next scheduled `3817` ` token`, next verifier token was `3817` ` token`, next emitted `3817` ` token`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 1 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 2 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 3 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 4 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 5 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 6 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 7 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 8 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-88255c4cb8154477-0-87ee40e0` | 9 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` | 10 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` | 11 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` | 12 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` | 13 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a0dc3825b6d6cf2f-0-b8e482e0` | 14 | 2 | 1 | 0 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
