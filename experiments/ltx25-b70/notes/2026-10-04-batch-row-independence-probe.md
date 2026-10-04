# One transformer pass for two or four clips: each clip's result depends only on its own inputs (probe, 2026-10-04)

Offline, one card at a time, no server. Script `scripts/probe-batch-row-independence.py`; results in
`data/batch-row-independence/`. Kernel 7.0.0-39, torch 2.14.0+xpu, the packet 95 ComfyUI tree with the
server's flags (bf16, strict determinism).

## In plain words

The sampler's cost is mostly reading the transformer's weights, once per forward, per clip. If one forward
carries two or four clips, the weights are read once for all of them. Packet 72 (September) closed this idea
because a clip computed in a batch of two is not byte-identical to the same clip computed alone, and it read
the size of the difference as "not rounding".

This probe shows that reading was wrong:

- **At batch sizes 2 and 4, a clip's result is bit-for-bit independent of the other clips in the batch and of
  its position in the batch.** Change the neighbours: same bits. Move the clip to another slot: same bits.
  Put the same clip in every slot: every row identical. Run it again: same bits.
- **Batch size 3 fails** the slot and identical-row tests (rows get different rounding depending on position),
  so it is not usable.
- **Against the clip computed alone, the difference is rounding.** About 40-60 % of the output values differ,
  by 0.1-0.3 % of the output's typical size on average (two unrelated clips differ by several hundred percent
  on the same scale). The cause is known from the text-window work: on this stack a matrix product rounds
  differently depending on how many rows it processes.

So at a fixed batch size, a clip's bytes depend only on its own prompt and seeds. It is the same mathematics
with different rounding: the same kind of change as the text window (milestone of 2026-10-04), not a new
approximation. It is still an output change against the current references, so adopting it is the owner's
decision.

## What was run

The real checkpoint's first 12 (run 1, card 0) or 16 (run 2, card 1) blocks, loaded through ComfyUI's own
loader, driven through the real sampler nodes of the workflow (two stages, 8 + 3 steps, euler ancestral,
cfg 1.0), eager, with seeded random conditioning of the real shape. In each forward the real inputs (clip A)
were stacked with other clips (different latent and different text context, same sigma) and compared.

| Test, per forward | Batch 2 | Batch 3 | Batch 4 |
| --- | --- | --- | --- |
| A's row unchanged when the other rows change | yes | yes | yes |
| A's row unchanged when A moves to another slot | yes | **no** | yes |
| Identical inputs in every slot give identical rows | yes | **no** | yes |
| Same batch twice gives the same bits | yes | yes | yes |
| A's row equal to A computed alone | no | no | no |
| Forwards checked | 2 (run 1) + 11 (run 2) | 2 (run 1) | 2 (run 1) + 11 (run 2) |

Run 2 covered all 11 sampler steps; every check passed on every step for batch 2 and batch 4.

Difference from the clip computed alone (run 2, video output; typical size of the output about 8, largest
value about 33):

| | mean difference | largest difference | values that differ |
| --- | ---: | ---: | ---: |
| Batch 2, steps 1-7 | 0.007-0.011 | 0.125 | 37-44 % |
| Batch 2, last step of stage 1 | 0.023 | 0.375 | 61 % |
| Batch 2, stage 2 (3 steps) | 0.012-0.025 | 0.125-0.375 | 48-64 % |
| Batch 4, all steps | 0.011-0.027 | 0.125-0.5 | 47-67 % |
| Two unrelated clips | several | 32-56 | all |

## What it does not show

- **Speed.** The probe runs eagerly, where every forward takes the same 100 ms regardless of batch size
  because issuing kernels from Python sets the pace. That says nothing about the server, which replays captured
  graphs. From the September block timings (2.74 ms per block at 64 video tokens, 3.61 ms at 256) a batch of
  two should cost roughly 1.3 times one forward, a batch of four roughly 1.9 times: an estimated 35 % and 50 %
  less sampler GPU time per clip. That estimate needs the real measurement.
- **The full model.** 12-16 of 48 blocks, no graph capture, no latent upsampler, and all rows at the same
  sigma (the model has one operation that mixes rows if their timesteps differ, so rows must run in lockstep).
  The packet 96 runner repeats the neighbour and slot tests in the real server on whole clips.
- **Picture quality.** Rounding-level differences give a different "take" after 11 steps, as the text window
  did. The packet 96 summary reports each clip's closeness to today's references.

## Correction to packet 72

[Packet 72](graph-capture-72-results.md) said the batch-2 difference was "by amounts that are not rounding"
and that something in the forward was batch-dependent. Its largest difference (0.18 on the first forward) is
within what this probe measures as rounding, and it did not test whether a row depends on its neighbours. The
neighbour and slot tests here show the forward is row-independent at batch 2 and 4. Packet 71's larger
difference came from rows with different timesteps.

## Next

Packet 96 (being built): a server option that runs B = 2 or 4 consecutive clips through one sampler job, with
new references made at that batch size, in-server neighbour and slot proofs on whole clips, and a timed arm.
