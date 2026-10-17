# Reading long prompts in bigger exact-cache pieces (preregistration, 2026-10-16 20:25 EDT)

## Question

The exact prefix cache reads every prompt in one-block steps (832 tokens on this model), so that a read resumed from
a cache hit computes block k with the same kernel call as a cold read. The cost, measured 2026-10-05: cold reads
are 16-33 % slower than in 4,096-token steps (30K 11.4 s, 120K 69.8 s, 200K 152 s against about 9.8 s, 54.8 s and
114 s; `2026-10-05-context-research-results.md`, edit-cost table). The extra time per step grows with the context
already read. Does a bigger block, still one block per step, keep the cache exact and remove most of that cost?

## Mechanism (source reading, delegated; checked by hand in the kernel source)

The prompt-attention kernel (`vllm-xpu-kernels` `csrc/xpu/attn/xe_2/chunk_prefill*.hpp`, policy `chunk_policy_head256`
in `fmha_utils.hpp`) gives each work-group 256 query rows of one head, with no split over the keys; the grid is
ceil(step/256) x 12 heads per card (TP2). Each work-group reads the whole context. An 832-token step is 4 x 12 = 48
work-groups on 32 Xe cores: two waves, the second half empty (and the 4th tile is three quarters padding). A
4,096-token step is 192 = six full waves. Per prompt token that is 2/832 against 6/4096 waves: 1.64 times the
attention time, and attention grows with the context, as the penalty does. A waves x context fit to the 4,096-step
reads alone predicts the nine 832-step reads within 0.02 s per step with no other per-step term, so the cache, the
align mode and the overlays add nothing measurable. (Write-up: scratch `piece-penalty-findings.md`, summarized
here; the MTP drafter's pass over each chunk uses the same kernel.)

Blocks of 1,280 tokens: 5 x 12 = 60 work-groups, still two waves (94 % full); 2,048: 96, three full waves. vLLM takes a
user `--block-size` for this hybrid model if it is a multiple of 64 and holds a recurrent state
(`platforms/interface.py:_align_hybrid_block_size`, `platforms/xpu.py:387`); the exact-cache overlay uses the
engine's block size, not a constant.

## Arms (runner `scripts/run-20261016-fp8-piece-size.sh`, one unattended session)

The context-lane server of campaign 24 (TP2, one sequence, MTP 5 with the INT4 draft head and shortlist, 262,144
window, align prefix cache, `b70-prefix-cache-exact`, `b70-spec-resume-accepted` 0.5.0, gdn-state-width,
exclusive-prefill, allgather-allreduce, chunked-upload); the only change is the piece size:

| Arm | Block = step | Kept state every |
| --- | --- | --- |
| K832 (control) | 832 (engine default) | 13,312 |
| K1280 | 1,280 (`--block-size 1280 --max-num-batched-tokens 1280`) | 12,800 |
| K2048 | 2,048 | 12,288 |

Round 1, one server each, in that order: `qwen38-fp8-edit-cost-probe.py` at 30K, 120K, 200K (cold read, the same
text again, four lines removed in the last block and at 90 %, 50 %, 10 %, each edit sent twice; the probe now also
records the eight answer tokens), then the 64-prompt order probe: K1280 and K2048 paused twice (S1, S2) and back to
back once (B1); K832 paused once (timing only, its exactness was settled today). Round 2: fresh servers for K832 and
the round-1 winner (the arm whose 200K cold read beats K832's by at least 10 %, the faster if both), edit-cost probe
again. Gemma stopped first and restored at the end unless a GPU fault line was logged.

## Predictions

- 200K cold read: K832 about 152 s; K1280 about 118 s; K2048 about 114 s or a little less. 120K: about 70 / 57 / 55 s.
  30K: about 11.4 / 10 / 9.8 s.
- Same text again and the edit in the last block re-read more (up to two blocks after the hit): at 200K about 1.8 s
  on K832, 2.5 s on K1280, 3.5 s on K2048.
- Exactness on K1280 and K2048: S1 = S2 = B1 (64/64 each). The edit probe's cold and repeat answers equal per length.
- Risk: K2048 may not start at 262K (each kept state holds the memory of 6,144 context tokens instead of 2,496).

## Decision rule

Adopt a bigger piece for the context lane only if: S1 = S2 = B1 64/64; the edit probe's cold, repeat and edited
answers agree with their repeats; the 120K and 200K cold reads are at least 10 % faster than K832 on both rounds
(two fresh servers each); and the repeat and last-block edit waits at 200K stay under 5 s. A new piece size changes
the arithmetic (answers may differ from the 832 servers at near ties), so its task results start from new
references; the lab's published context results stay on 832 until re-run. Speed is recorded, never an identity gate.
If no arm qualifies, the lever closes with these numbers; the next candidates are a split-key prompt-attention kernel
with fixed split points, and skipping the drafter's four discarded single-token passes on non-final prompt chunks
(estimated 1-5 s at 200K).

Launched 20:07:53 EDT (unit `fp8-piece1`, log `data/2026-10-16-r314-piece-size/run.log`). The edit probe needs the
`tokenizers` library, which the host's system Python lacked; it was copied at 20:09, before the first probe ran, from
`/mnt/fast-ai/venvs/minimax-h3` (0.23.2, same Python 3.12.3) into `~/.local/lib/python3.12/site-packages`.

## Amendment, 21:00 EDT (after round 1's edit probes, before round 2 ran)

Round 1 cold reads at 200K: K832 152.1 s, K1280 118.1 s, K2048 114.1 s; all three arms 15/15 cached = cold. The
round-2 rule picks K2048 (fastest cold read), but K2048 almost doubles the cost of a hit (repeat at 200K 3.2 s against
1.8 s on K832 and 1.9 s on K1280), and agent traffic is mostly hits. So the choice between 1,280 and 2,048 must weigh
the repeat cost, and both need a second fresh server: **round 2b** adds a fresh K1280b server with the edit-cost probe
only, run right after round 2 (`scripts/run-20261016-fp8-piece-size-r2b.sh`, unit `fp8-piece2b`). Decision: the
arm adopted for the context lane is the one with the lower 200K repeat wait among those that meet the 10 % cold-read
rule on both rounds; 2,048 only if its repeat wait is within 0.5 s of 1,280's.
