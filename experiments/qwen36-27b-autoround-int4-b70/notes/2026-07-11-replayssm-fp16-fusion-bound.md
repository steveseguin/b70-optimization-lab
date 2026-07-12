# ReplaySSM FP16 stage/recurrent fusion bound correction

The old stage-plus-recurrent pre-gate used BF16 target/state assumptions and
summed separately synchronized regions. It was refreshed at the promoted TP2
shape: FP16 target activations, FP32 SSM state, one sequence, spec length 4,
cache length 8, eight local K heads, and 24 local V heads.

Across four B70s, 2,000 iterations each:

- stage-conv mean: `17.294 us/layer`;
- recurrent mean: `30.909 us/layer`;
- queued stage-then-recurrent mean: `37.664 us/layer`.

The effective incremental stage cost over recurrent is therefore only about
`6.755 us/layer`, or **`0.324 ms/step`** across 48 GDN layers. The kernels
overlap enough that summing their standalone times overstates the fusion
opportunity. At the current `95.385 tok/s` and about `2.747` visible
tokens/step, reaching 100 requires roughly `1.33 ms/step`; eliminating the
entire incremental stage cost would cover only about one quarter of that.

Decision: do not build a large monolithic stage/recurrent kernel solely for
the 100 tok/s goal. Reopen only as part of a broader recurrent redesign that
also reduces required arithmetic, not merely the intermediate launch/buffers.

Tracked result:
`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-stage-decode-fp16-fp32state-4gpu-20260711.json`.
