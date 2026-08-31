# Qwen3.8 Flash-Next FP8 EP partition/device rotation result

Date: 2026-08-31
Status: bounded component negative; no endpoint rank reordering

The A28 profile showed one rank arriving late through much of target decode.
After no-EP TP4 failed its component gate, this screen asked whether the delay
was tied to one physical B70 or one quarter of the 512-expert bank. The exact
layer-0 EP4 checkpoint fixture was run in a four-rotation Latin square so every
128-expert partition executed once on every physical card. The workload used
the same frozen top-10 route set and measured local MoE only, without allowing
the collective to hide rank-local timing.

The initial Latin square did not identify a slow partition or device marginal,
but independent review correctly found that its single slow
partition-1/device-1 cell was confounded with an unreplicated interaction.
Partition medians were
`413.779 / 409.794 / 413.915 / 412.523 us`; physical-device medians were
`411.290 / 414.428 / 412.281 / 413.091 us`. One partition-1/device-1 cell ran
at `446.734 us`. Each cell was internally repeatable, and each expert partition
retained the same output hash on all four devices, but the initial screen alone
could not call that interaction transient.

The frozen A2 correction repeated partition-1/device-1 four times, paired by
cycle with partition-1/device-0 and partition-0/device-1 controls. Its penalties
against the slower matched control were `-2.075 / -5.532 / +0.881 / +0.442%`:
zero of four exceeded the frozen 5% interaction gate. The suspect cell median
was `415.807 us`; cross-cell partition hashes remained exact. This replicate,
not the original unreplicated marginal comparison, closes the mapping effect.

Do not spend a full-model load on rank reordering. The endpoint imbalance is
dynamic across layers/cycles or caused by scheduling ahead of the MoE call,
not a fixed bad card or fixed expert quarter that a static device order can
repair. Structured results and the external evidence manifest are in
[`20260831-tp4-mtp0-ep4-partition-device-latin-square-negative.json`](../data/20260831-tp4-mtp0-ep4-partition-device-latin-square-negative.json).
The corrective evidence is in
[`20260831-tp4-mtp0-ep4-partition-device-interaction-replicate-negative.json`](../data/20260831-tp4-mtp0-ep4-partition-device-interaction-replicate-negative.json).
