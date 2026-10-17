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

## Result, round 1 (20:07-21:09 EDT, one server each, kernel log clean)

Wait for the first token (s), edit-cost probe (`data/2026-10-16-r314-piece-size/edit-K*.json`):

| Request | K832 | K1280 | K2048 |
| --- | ---: | ---: | ---: |
| 30K cold | 11.5 | 10.1 | 10.2 |
| 30K same text again | 0.8 | 0.8 | 1.3 |
| 30K edit in the last block | 0.7 | 1.6 | 1.2 |
| 120K cold | 69.4 | 56.4 | 54.6 |
| 120K same text again | 1.6 | 1.6 | 2.2 |
| 120K edit at 50 % | 46.5 | 37.5 | 37.2 |
| 200K cold | **152.1** | **118.1** | **114.1** |
| 200K same text again | 1.8 | 1.9 | 3.2 |
| 200K edit in the last block | 15.8 | 7.1 | 3.0 |
| 200K edit at 90 % | 30.6 | 28.0 | 22.9 |
| 200K edit at 50 % | 102.9 | 79.5 | 113.9 |

- K832 repeats the 2026-10-05 table within 0.4 s on every cold read (11.4 / 69.8 / 152 then).
- Predictions held: K1280's 200K cold read was predicted at about 118 s and came in at 118.1 s; K2048 at 114.1 s.
  The wave model is right.
- **Exactness:** every arm 15/15 (each cached repeat and each edited text sent again gives the same eight tokens).
  K1280 and K2048: paused twice and back to back all 64/64. Across arms (different arithmetic): K832 against K1280
  62/64 (two `prose2k` copies that never touch the cache differ at token 93, a near tie from the step size); the
  30 eight-token edit-probe answers are the same on all three arms.
- **Short prompts with hits** (the 64-prompt pass, 2K-8K prompts, 128 tokens): 183 s on K832, 189 s on K1280, 200 s
  on K2048 (fewer cached tokens per hit: 209,664 / 179,200 tokens over the pass).
- K2048's middle-of-text edit at 200K is slower (113.9 s) because its kept states (every 12,288 tokens) put the 50 %
  edit's resume point further back; K1280 and K832 resume within 1 block of a kept state there.

Round 1's winner by the registered rule is K2048 (114.1 s against 152.1 s, -25 %); K1280 also passes (-22 %).
Round 2 (fresh K832b and K2048b) and round 2b (fresh K1280b) are running.

## Part E, registered 21:50 EDT before any run: the agent stream (campaign 25)

The edit probe reads whole texts; agent traffic is mostly cache hits plus a few thousand new tokens per call, where
bigger blocks re-read more after each hit. Campaign 25 runs ctxkeeper 1.1.0 on the 240K rules stream, seed 0, at
two working windows, K32 (32,768 budget; campaign 24c: 39/39 in 8 min 41 s on a two-sequence server) and K64
(65,536), on two servers that differ only in the piece: c25a PIECE=832, c25b PIECE=1280 (one sequence, MTP 5,
campaign 24's flags otherwise; runner `data/2026-10-16-context-campaign25/longrun-campaign25.sh`, queue
`QUEUE25.txt`). Queued after round 2b.

Predictions: both arms 39/39 on both servers. K32 time on c25b within 5 % of c25a either way (contexts up to 32K:
the cold part reads about 12 % faster, each hit re-reads about 450 more tokens on average). K64 a few % faster on
c25b. Decision: switch the context lane's default piece to 1,280 only if K64 is faster and K32 no more than 3 %
slower, both with full scores; otherwise 1,280 is kept as the long-document profile (reading 100K+ at once) and the
agent default stays 832.

## Result, rounds 2 and 2b (21:10-21:56 EDT, three more fresh servers, kernel log clean)

Every fresh server repeats its round-1 twin within 0.2 s on every request (`edit-K832b/K1280b/K2048b.json`):

| Request, 200K unless noted | K832 / K832b | K1280 / K1280b | K2048 / K2048b |
| --- | ---: | ---: | ---: |
| 120K cold | 69.4 / 69.6 | 56.4 / 56.2 | 54.6 / 54.6 |
| cold | 152.1 / 152.2 | 118.1 / 118.1 | 114.1 / 114.1 |
| same text again | 1.8 / 1.8 | 1.9 / 1.9 | 3.2 / 3.2 |
| edit in the last block | 15.8 / 15.9 | 7.1 / 7.1 | 3.0 / 3.0 |
| edit at 50 % | 102.9 / 103.0 | 79.5 / 79.5 | 113.9 / 114.1 |

- **Exactness:** all six servers 15/15 cached = fresh; each piece size's two servers give the same 30 answers
  (30/30), and the 30 answers are also the same across the three piece sizes.
- **Cold reads:** 1,280 is 19 % faster than 832 at 120K and 22 % at 200K, on both servers; 2,048 is 21 % and 25 %.
  Both meet the 10 % rule twice.
- **The amendment's pick is 1,280:** its 200K repeat wait is 1.9 s against 3.2 s for 2,048 (1.3 s apart, more than
  the 0.5 s allowance), at 4 s more on a 200K cold read.
- **One registered gate is missed, by every arm but 2,048, the control worst:** "the last-block edit at 200K under
  5 s". 1,280 takes 7.1 s, 832 takes 15.8 s. The gate assumed the re-read after a hit is at most two blocks; the
  cached-token counts show it starts from the nearest kept state instead, at a multiple of the kept-state interval:
  186,368 = 14 x 13,312 on 832 (13,138 tokens re-read), 192,000 = 15 x 12,800 on 1,280 (7,506), 196,608 =
  16 x 12,288 on 2,048 (2,898). So that wait measures where the kept-state grid happens to fall against this text's
  length, not the piece size (the same edited text sent again: 2.2 / 2.5 / 3.0 s). I do not re-read the rule to
  pass 1,280; I record the miss and leave the choice of the agent default to part E, registered for that purpose.

Outcome: 1,280-token pieces are the faster long-document setting (a 200K read 34 s shorter, everything exact); the
agent default waits for campaign 25. A separate lever this exposes: the cost of an edit near the end is set by the
kept-state interval (memory per kept state against re-read length), untested here.

### The drafter's discarded passes, sized on paper (22:05 EDT; no GPU run)

R314 runs the drafter on every step, including steps where every request is a non-final prompt chunk
(`gpu_model_runner.py` `sample_tokens`: `propose_draft_token_ids` is called whenever the input fits; no
`_is_all_reqs_chunked_prefill` check, which is only used for pipeline-parallel broadcasts). Pass 1 must run (it
writes the drafter's cache for the chunk); passes 2-5 are single-row passes whose drafts are thrown away. Their cost:
the 2026-10-03 table puts all of speculation (five draft passes plus five extra verify rows) at 3.5 ms per step on
two cards, so a single-row pass is under 0.7 ms, plus about 0.4 ms at 200K for the drafter layer's attention over
the context. At 1,280-token pieces a 200K read is 156 chunks x 4 passes x about 1 ms = about 0.6 s of 118 s
(0.5 %); at 832, about 1 s of 152 s. Below the 1-5 s guessed above, and below run-to-run noise on a single read. Not
worth a GPU run alone; it can ride along with the next overlay change that needs a full exactness run anyway.

### Where an agent stream's time goes (22:15 EDT, from campaign 24c's K32 call log, before part E's results)

`proxy-state/c24c-K32-rules-s0/*/calls.jsonl` (182 calls, two-sequence server, 832 pieces), least-squares split of each
call's time into reading the uncached prompt, writing, and a fixed part: main calls 289 s = reading 128 s (0.27 ms per
uncached token) + writing 122 s (9.3 ms per token) + 39 s fixed; notes calls 182 s, almost all writing (17,146
tokens, 11 ms each). So about two thirds of the run is writing and 28 % reading. Of the 481K uncached tokens in main
calls, 179K are the short re-read after each hit (about 1,100 tokens per call: the rest of the last block plus the
previous answer), which a bigger piece lengthens, and 70K are 20 whole-window re-reads of about 3.7K tokens right
after each notes update (`cached 0`: the new window shares only the system prompt and rules, about 1.4K tokens, and
no kept state lies inside them), about 30 s of 517. The piece size can move at most the reading part, so part E
should show a few per cent either way.

## Result, part E (campaign 25, 22:00-23:04 EDT; kernel log clean; data `data/2026-10-16-context-campaign25/`)

| Arm | Piece 832 (c25a) | Piece 1,280 (c25b) |
| --- | --- | --- |
| K32 | 39/39, 8 min 42 s | 39/39, 8 min 40 s |
| K64 | 39/39, 9 min 56 s | 39/39, 10 min 47 s |
| K32 main calls: tokens read uncached / written | 481,173 / 13,103 | 571,780 / 13,432 |
| K32 notes calls: tokens written | 17,146 | 15,314 |
| K64 main calls: tokens read uncached / written | 473,349 / 11,500 | 580,833 / 13,727 |
| K64 notes calls: tokens written | 18,319 | 21,027 |

**Decision by the registered rule: the agent default stays at 832.** K64 is 8.6 % slower on 1,280 (rule: switch only
if K64 is faster). 1,280 stays the long-document setting (reading 100K+ at once).

- Scores full on all four (the predictions held there). K32 within 0.4 %, predicted within 5 %; K64 predicted a few %
  faster, came in 8.6 % slower.
- Why: each hit re-reads more with bigger pieces, as expected (+19 % and +23 % uncached tokens in main calls), and the
  two servers' different arithmetic sends the stream down different text paths, so the amount written differs: K32
  wrote 1,500 fewer tokens on 1,280, K64 4,900 more (about +55 s at 11 ms a token, all of K64's 51 s gap). Writing
  dominates these runs, so a single seed cannot separate a 3 % reading effect from the text-path difference; with
  writing held equal, 1,280 is about 15 s slower on K32 and about even on K64. Either way no gain for agent traffic.
- The 832 server repeats campaign 24c's notes exactly on K32 (17,146 tokens written, same cuts) although 24c ran on a
  two-sequence server: the stream is deterministic for a given piece.

Lever closed for the agent default. Next on the reading side: the prompt-attention kernel itself (about 70 TFLOPS of
the card's FP16 peak at 200K, from the waves fit), measured alone first (`scripts/bench-chunk-prefill-attn.py`).
