# Packet104 boundaries

| Arm or assumption | Outcome / condition |
| --- | --- |
| Use packet59 draft kernels as packet100's selected baseline | Rejected by selection/dispatch audit. Packet100 selects mtp36 WG128, plus packet33 WG32 shared-down. The first build is retained as superseded preparation. |
| Infer locality counters from packet100's timing improvement | No DRAM page-hit or L3 counter evidence. These are mechanisms to test, not measured explanations. |
| Call target-route replay a native draft-route measurement | Incorrect. The supplied packet100b target IDs are replayed through draft, as an operator diagnostic. Actual model screens decide transfer. |
| Advance on an overall median only | Refused: require <=0.85 overall, in both orders and every route/input stratum. |
| Run full byte/startup/VRAM/seal work before a measured micro win | Deferred by the user. Prepared integration files and selections are not qualified builds. |
| Use the model's resident-only target selection for KD's draft-only host path | Refused. The planned host reference retains the selected draft and removes target-only layouts. Every real chain-window startup remains mandatory. |
| Transpose target shared/router weights by name when a partial plan lacks the full tuple | Rejected in static review. Load and dispatch share complete-tuple coverage; any outside consumer keeps the whole selected bank set in its original layout. Full startup validation remains pending. |
| Repeat packets 95/99/102 lookup, prefetch or batching variants | Closed. This packet rearranges immutable weight bytes only. |

No performance candidate is closed before device measurements. No full model
speed, output identity, exact draft acceptance or record eligibility is claimed.

## Packet104b coordinator decision, 2026-10-18

The original <=0.85 micro gate failed for every arm. The coordinator explicitly
waived that *performance threshold only* for one screen grid of the two TARGET
gate/up arms. This does not waive byte identity, startup, memory, exact model
outputs, acceptance counts, or fresh controls. See [override](screening-override.json)
and [micro closeout](micro-closeout.md).

| Arm | Candidate/control time | Decision |
| --- | ---: | --- |
| target-gate-tile16 | 0.898048 | One screen under explicit coordinator override; no micro pass or engine gain claimed. |
| target-gate-halfcache-tile16 | 0.892953 | Same override; exact FP32 weight-scale cache, never compressed KV. |
| target-shared-q6-tile16 | 0.950510 | Closed: below 15% improvement; no override. |
| hc-gate-tile16 | 1.006565 | Closed: slower; no override. |
| target-router-tile16 | 1.026424 | Closed: slower; no override. |
| draft-gate-tile16 | 1.261494 | Closed: slower target-route replay diagnostic. |
| draft-down-tile16 | 1.346788 | Closed: slower target-route replay diagnostic. |
| shared-gate-up-tile16 | 1.496321 | Closed: slower; no override. |
| shared-down-tile16 | 2.094842 | Closed: slower; no override. |
| Reuse packet104's old baseline as packet97's selected composition | Refused: old baseline omitted route-fast, rec-both-plus and E1. Packet104b snapshots packet97's actual selection locally and adds down-tile16. |
| Claim plain gate-tile16 isolates the transpose against E1 control | Refused: this arm removes E1. The halfcache-tile16 arm retains E1 and isolates transpose. |

Closed arms require a materially new mechanism or explicit coordinator decision,
not another run of the same layout. Earlier deferred-CPU wording above is
superseded only for the two named gate/up arms.
