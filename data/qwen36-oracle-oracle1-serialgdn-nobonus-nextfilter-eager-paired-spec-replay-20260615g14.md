# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-nobonus-nextfilter-eager-paired-20260615g14-spec-trace.jsonl`
- rows: `28`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `25`
- suppressed schedule mismatches: `25`
- suppressed accept mismatches: `25`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-951d349832e28038-0-ade216a9` | 16 | 16 | 16 | 0 | 16 | `repetitive_kernel_notes (scheduler_prefix)` | 15 | 15 | 15 | 0 |
| `cmpl-82f4bbd0bf52b7dd-0-b417a974` | 12 | 12 | 10 | 2 | 10 | `natural_latency_plan (scheduler_prefix)` | 10 | 10 | 10 | 0 |

## Suppressed Follow-Up Mismatches

- request `cmpl-951d349832e28038-0-ade216a9` line `13` -> `14`:
  suppressed `13` `.`, next scheduled `78503` ` Preserve`, next verifier token was `78503` ` Preserve`, next emitted `78503` ` Preserve`.
- request `cmpl-951d349832e28038-0-ade216a9` line `14` -> `15`:
  suppressed `4581` ` exact`, next scheduled `2468` ` output`, next verifier token was `2468` ` output`, next emitted `2468` ` output`.
- request `cmpl-951d349832e28038-0-ade216a9` line `15` -> `16`:
  suppressed `1345` ` while`, next scheduled `28043` ` measuring`, next verifier token was `28043` ` measuring`, next emitted `28043` ` measuring`.
- request `cmpl-951d349832e28038-0-ade216a9` line `16` -> `17`:
  suppressed `7072` ` multi`, next scheduled `3817` ` token`, next verifier token was `3817` ` token`, next emitted `3817` ` token`.
- request `cmpl-951d349832e28038-0-ade216a9` line `17` -> `18`:
  suppressed `22188` ` verification`, next scheduled `13` `.`, next verifier token was `13` `.`, next emitted `13` `.`.
- request `cmpl-951d349832e28038-0-ade216a9` line `18` -> `19`:
  suppressed `15153` ` Intel`, next scheduled `1543` ` X`, next verifier token was `1543` ` X`, next emitted `1543` ` X`.
- request `cmpl-951d349832e28038-0-ade216a9` line `19` -> `20`:
  suppressed `6126` `PU`, next scheduled `16401` ` decode`, next verifier token was `16401` ` decode`, next emitted `16401` ` decode`.
- request `cmpl-951d349832e28038-0-ade216a9` line `20` -> `21`:
  suppressed `85683` ` verifier`, next scheduled `15162` ` bucket`, next verifier token was `15162` ` bucket`, next emitted `15162` ` bucket`.
- request `cmpl-951d349832e28038-0-ade216a9` line `21` -> `22`:
  suppressed `5832` ` route`, next scheduled `4618` ` graph`, next verifier token was `4618` ` graph`, next emitted `4618` ` graph`.
- request `cmpl-951d349832e28038-0-ade216a9` line `22` -> `23`:
  suppressed `3817` ` token`, next scheduled `17856` ` timing`, next verifier token was `17856` ` timing`, next emitted `17856` ` timing`.
- request `cmpl-951d349832e28038-0-ade216a9` line `23` -> `24`:
  suppressed `13` `.`, next scheduled `78503` ` Preserve`, next verifier token was `78503` ` Preserve`, next emitted `78503` ` Preserve`.
- request `cmpl-951d349832e28038-0-ade216a9` line `24` -> `25`:
  suppressed `4581` ` exact`, next scheduled `2468` ` output`, next verifier token was `2468` ` output`, next emitted `2468` ` output`.
- request `cmpl-951d349832e28038-0-ade216a9` line `25` -> `26`:
  suppressed `1345` ` while`, next scheduled `28043` ` measuring`, next verifier token was `28043` ` measuring`, next emitted `28043` ` measuring`.
- request `cmpl-951d349832e28038-0-ade216a9` line `26` -> `27`:
  suppressed `7072` ` multi`, next scheduled `3817` ` token`, next verifier token was `3817` ` token`, next emitted `3817` ` token`.
- request `cmpl-951d349832e28038-0-ade216a9` line `27` -> `28`:
  suppressed `22188` ` verification`, next scheduled `13` `.`, next verifier token was `13` `.`, next emitted `13` `.`.
- request `cmpl-82f4bbd0bf52b7dd-0-b417a974` line `1` -> `2`:
  suppressed `47193` ` numbered`, next scheduled `14246` ` engineering`, next verifier token was `14246` ` engineering`, next emitted `14246` ` engineering`.
- request `cmpl-82f4bbd0bf52b7dd-0-b417a974` line `2` -> `3`:
  suppressed `8129` ` notes`, next scheduled `13` `.`, next verifier token was `13` `.`, next emitted `13` `.`.
- request `cmpl-82f4bbd0bf52b7dd-0-b417a974` line `3` -> `4`:
  suppressed `24985` ` Focus`, next scheduled `383` ` on`, next verifier token was `383` ` on`, next emitted `383` ` on`.
- request `cmpl-82f4bbd0bf52b7dd-0-b417a974` line `4` -> `5`:
  suppressed `3074` ` single`, next scheduled `43318` `-request`, next verifier token was `43318` `-request`, next emitted `43318` `-request`.
- request `cmpl-82f4bbd0bf52b7dd-0-b417a974` line `5` -> `6`:
  suppressed `16401` ` decode`, next scheduled `4478` ` speed`, next verifier token was `4478` ` speed`, next emitted `4478` ` speed`.
- request `cmpl-82f4bbd0bf52b7dd-0-b417a974` line `6` -> `7`:
  suppressed `11` `,`, next scheduled `29541` ` reliability`, next verifier token was `29541` ` reliability`, next emitted `29541` ` reliability`.
- request `cmpl-82f4bbd0bf52b7dd-0-b417a974` line `7` -> `8`:
  suppressed `33389` ` gates`, next scheduled `11` `,`, next verifier token was `11` `,`, next emitted `11` `,`.
- request `cmpl-82f4bbd0bf52b7dd-0-b417a974` line `8` -> `9`:
  suppressed `11436` ` hardware`, next scheduled `4581` ` exact`, next verifier token was `874` ` no`, next emitted `874` ` no`.
- request `cmpl-82f4bbd0bf52b7dd-0-b417a974` line `10` -> `11`:
  suppressed `4557` ` loss`, next scheduled `13` `.`, next verifier token was `13` `.`, next emitted `13` `.`.
- request `cmpl-82f4bbd0bf52b7dd-0-b417a974` line `11` -> `12`:
  suppressed `271` `

`, next scheduled `760` `The`, next verifier token was `248068` `<think>`, next emitted `248068` `<think>`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-951d349832e28038-0-ade216a9` | 13 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 14 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 15 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 16 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 17 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 18 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 19 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 20 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 21 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 22 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 23 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 24 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 25 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 26 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 27 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-951d349832e28038-0-ade216a9` | 28 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-82f4bbd0bf52b7dd-0-b417a974` | 1 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-82f4bbd0bf52b7dd-0-b417a974` | 2 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-82f4bbd0bf52b7dd-0-b417a974` | 3 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-82f4bbd0bf52b7dd-0-b417a974` | 4 | 2 | 1 | 0 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
