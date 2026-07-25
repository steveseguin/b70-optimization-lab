# Laguna M8 persistent exact-attention metadata result

Date: 2026-07-25

## Result

The v2 persistent-metadata diagnostic passed completely and is authorized to
advance to a separately preregistered uninstrumented formal crossover. It is
diagnostic-only and is not LocalMaxxing-submittable.

Sealed internal-NVMe root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-persistent-attn-metadata-dd1619dca-ef334233d-20260725T013440Z
```

Analysis SHA-256:

```text
8b3ac0676349e0e8bfef7b5603c67ceb189bc0e93a8292859ef71cdb45819020
```

Frozen source:

- main gate `dd1619dca004ec1e121d2ab22d69a16ab60faf14`;
- vLLM `ef334233deabeaeedb607056a2db1c90edb3887c`;
- kernels `4772f727590c51b72add79350b913d098cf67872`.

## Exactness and hygiene

q1, eager, and graph each ran one fresh 272-token generation in a separate
process. Every arm reported cached tokens zero and finish reason `length`.
All three matched bitwise:

```text
token ee44dfe987c199b248cfe8f752f5fa8600a34291815894c5fb6502ffd5187cee
text  d41518e5781b3adafb966c1b9a91e46d4d23b1a1ef40d8992ccde9a55920e55f
```

All pre/post worker reports were empty and all strict-idle snapshots passed.
The models and artifacts remained on internal ext4 NVMe.

All four ranks retained 31 replay samples with the frozen topology:

- 146 graph segments;
- 145 eager boundaries: 48 attention and 97 collective;
- segment-order SHA-256
  `e5b64443ef499d8bb8b138a94ad504effeaa6434a8884ae9f885aecf12d34e1b`.

## Timing

The authoritative incumbent is the earlier exact 272-token decomposition at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-inprocess-replay-17769a57d-8cf58ed0f-20260725T002351Z
```

Median maximum-rank comparison:

| Measure | Incumbent | v2 | Saving |
|---|---:|---:|---:|
| 48 attention calls | 8.117824 ms | 4.117625 ms | 4.000199 ms, 49.28% |
| replay host total | 16.724431 ms | 12.163295 ms | 4.561136 ms, 27.27% |
| post-replay sync | 6.136466 ms | 9.507746 ms | −3.371280 ms |
| whole replay | 21.543770 ms | 21.137799 ms | 0.405971 ms, 1.88% |

The 272-token graph generation call decreased from `22.015380267 s` to
`21.915757354 s`, a `0.4525%` diagnostic reduction.

The candidate therefore removed the intended repeated host construction work.
Most of the saved host enqueue time became outstanding device work observed at
the final synchronization, so the end-to-end gain is much smaller than the
attention-boundary gain. The whole-replay median nevertheless improved
materially and did not merely regress after the cost shift.

Static signature collection plus comparison remained small at a combined
median `0.399792 ms`; the additional fixed-address candidate fields did not
erase the end-to-end win.

## Decision

Preregister one uninstrumented cold formal crossover against the approved
`92.16352215694299 tok/s` record. The expected endpoint effect is small enough
that variance can decide an individual leg, so promotion must use the existing
fail-closed crossover design and frozen thresholds. No diagnostic timing or
generation-wall number may be submitted.
