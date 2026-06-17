# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-oracle1-nobonus-eager-20260615g18-spec-trace.jsonl`
- rows: `22`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `20`
- suppressed schedule mismatches: `20`
- suppressed accept mismatches: `20`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 15 | 15 | 15 | 0 | 15 | `repetitive_kernel_notes (scheduler_prefix)` | 14 | 14 | 14 | 0 |
| `cmpl-9e26abda30174e31-0-9543627b` | 7 | 7 | 7 | 0 | 7 | `natural_latency_plan (scheduler_prefix)` | 6 | 6 | 6 | 0 |

## Suppressed Follow-Up Mismatches

- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `8` -> `9`:
  suppressed `13` `.`, next scheduled `78503` ` Preserve`, next verifier token was `78503` ` Preserve`, next emitted `78503` ` Preserve`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `9` -> `10`:
  suppressed `4581` ` exact`, next scheduled `2468` ` output`, next verifier token was `2468` ` output`, next emitted `2468` ` output`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `10` -> `11`:
  suppressed `1345` ` while`, next scheduled `28043` ` measuring`, next verifier token was `28043` ` measuring`, next emitted `28043` ` measuring`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `11` -> `12`:
  suppressed `7072` ` multi`, next scheduled `3817` ` token`, next verifier token was `3817` ` token`, next emitted `3817` ` token`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `12` -> `13`:
  suppressed `22188` ` verification`, next scheduled `13` `.`, next verifier token was `13` `.`, next emitted `13` `.`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `13` -> `14`:
  suppressed `15153` ` Intel`, next scheduled `1543` ` X`, next verifier token was `1543` ` X`, next emitted `1543` ` X`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `14` -> `15`:
  suppressed `6126` `PU`, next scheduled `16401` ` decode`, next verifier token was `16401` ` decode`, next emitted `16401` ` decode`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `15` -> `16`:
  suppressed `85683` ` verifier`, next scheduled `15162` ` bucket`, next verifier token was `15162` ` bucket`, next emitted `15162` ` bucket`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `16` -> `17`:
  suppressed `5832` ` route`, next scheduled `4618` ` graph`, next verifier token was `4618` ` graph`, next emitted `4618` ` graph`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `17` -> `18`:
  suppressed `3817` ` token`, next scheduled `17856` ` timing`, next verifier token was `17856` ` timing`, next emitted `17856` ` timing`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `18` -> `19`:
  suppressed `13` `.`, next scheduled `78503` ` Preserve`, next verifier token was `78503` ` Preserve`, next emitted `78503` ` Preserve`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `19` -> `20`:
  suppressed `4581` ` exact`, next scheduled `2468` ` output`, next verifier token was `2468` ` output`, next emitted `2468` ` output`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `20` -> `21`:
  suppressed `1345` ` while`, next scheduled `28043` ` measuring`, next verifier token was `28043` ` measuring`, next emitted `28043` ` measuring`.
- request `cmpl-84e99665b52a6dba-0-8a15ca2d` line `21` -> `22`:
  suppressed `7072` ` multi`, next scheduled `3817` ` token`, next verifier token was `3817` ` token`, next emitted `3817` ` token`.
- request `cmpl-9e26abda30174e31-0-9543627b` line `1` -> `2`:
  suppressed `27044` ` dense`, next scheduled `47193` ` numbered`, next verifier token was `47193` ` numbered`, next emitted `47193` ` numbered`.
- request `cmpl-9e26abda30174e31-0-9543627b` line `2` -> `3`:
  suppressed `14246` ` engineering`, next scheduled `8129` ` notes`, next verifier token was `8129` ` notes`, next emitted `8129` ` notes`.
- request `cmpl-9e26abda30174e31-0-9543627b` line `3` -> `4`:
  suppressed `13` `.`, next scheduled `24985` ` Focus`, next verifier token was `24985` ` Focus`, next emitted `24985` ` Focus`.
- request `cmpl-9e26abda30174e31-0-9543627b` line `4` -> `5`:
  suppressed `383` ` on`, next scheduled `3074` ` single`, next verifier token was `3074` ` single`, next emitted `3074` ` single`.
- request `cmpl-9e26abda30174e31-0-9543627b` line `5` -> `6`:
  suppressed `43318` `-request`, next scheduled `16401` ` decode`, next verifier token was `16401` ` decode`, next emitted `16401` ` decode`.
- request `cmpl-9e26abda30174e31-0-9543627b` line `6` -> `7`:
  suppressed `4478` ` speed`, next scheduled `11` `,`, next verifier token was `11` `,`, next emitted `11` `,`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 8 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 9 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 10 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 11 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 12 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 13 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 14 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 15 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 16 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 17 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 18 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 19 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 20 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 21 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-84e99665b52a6dba-0-8a15ca2d` | 22 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-9e26abda30174e31-0-9543627b` | 1 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-9e26abda30174e31-0-9543627b` | 2 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-9e26abda30174e31-0-9543627b` | 3 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-9e26abda30174e31-0-9543627b` | 4 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-9e26abda30174e31-0-9543627b` | 5 | 2 | 1 | 0 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
