# Packet 96 results: two clips per sampler job is proven row-independent in the real server (2026-10-04)

Packet `prepared-encoder-batch-96` (manifest `5822b050…`), runner `scripts/run-campaign-96.sh`, kernel
7.0.0-39, servers launched with `NEOReadDebugKeys=1 EnableDeferBacking=0`. Build and design:
[packet 96 build](2026-10-04-packet-96-build.md). Background:
[batch row-independence probe](2026-10-04-batch-row-independence-probe.md). Receipts: `data/batch-96/`.

## In plain words

One sampler job now carries two clips through the transformer together, so the model's weights are read once
for both. In the real server, with the whole model, graph replay and the latent upsampler:

- **Every clip came out byte-identical whatever clip it shared its batch with and whichever slot it sat in.**
  The ten fixtures were regenerated with other neighbours, then with swapped slots, then 115 more times in a
  stream where the pairing changes every cycle: 135 of 135 identical to their batch-2 references.
- **A batch-2 clip is not byte-identical to today's (batch-1) reference clip.** It is the same mathematics with
  different rounding, and after 11 sampler steps that gives a different take of the same prompt, as the
  text-window change did. Picture PSNR against today's references is 17-29 dB, the same range the window
  change produced. Whether to adopt batch-2 clips as the baseline is the owner's decision.
- **GPU work per clip fell by about a fifth** (2.93 compute-seconds per clip against 3.74), and that is with
  only one job in flight. This first run was the proof, not the speed run: with a single job the stream ran at
  1.414 s per clip, the same as before, with the sampler cards only 55-75 % busy.

## Run 1: two cards (23/25 blocks), one sampler job, batch 2, private pools

| Arm | Checked against | Clips checked | Exact | Seconds per clip (mean) | Sampler job (2 clips) | Compute seconds per clip, cards 0-3 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| reference (makes `stability-01-b2-*`) | – | – | – | 1.47 | 2.61 s | 0.60 / 0.82 / 0.26 / 0.55 |
| proof: other neighbours | batch-2 references | 10 | 10 | 1.47 | 2.61 s | 0.59 / 0.83 / 0.26 / 0.57 |
| proof: swapped slots | batch-2 references | 10 | 10 | 1.47 | 2.62 s | 0.76 / 1.03 / 0.26 / 0.61 |
| timed, 120 prompts, pairing changes every cycle | batch-2 references | 115 | 115 | **1.414** | 2.72 s | 0.80 / 1.06 / 0.35 / 0.72 |

- Capture pass, coverage, whole-chain replay check, freeze and self-check all passed at the first attempt.
  No refusal receipts, no GPU fault, no lockup. Clean stop.
- Video memory free at the freeze: 3.9 / 6.3 / 11.8 / 14.6 GiB. One batch-2 worker cost 4.3 GiB on card 0
  (0.18 GiB per block), about 1.5 times a batch-1 worker, not the 2 times the plan assumed.
- A sampler job for two clips takes 2.6-2.7 s. The stream alternates 0.2 s and 2.5 s between clips (they
  arrive in pairs); the mean is the throughput.

### How different are batch-2 clips from today's references?

Not a gate; reported so the difference can be judged. Each row compares the batch-2 reference clip with the
current (`w93c`) reference for the same prompt and seed.

| Fixture | Picture PSNR (dB) | Sound SNR (dB) |
| --- | ---: | ---: |
| boat | 18.6 | 1.9 |
| marble | 24.3 | 3.5 |
| bird | 18.0 | 0.4 |
| pendulum | 23.1 | 5.1 |
| rain | 26.4 | 2.1 |
| paper | 19.9 | 3.4 |
| candle | 17.1 | 4.3 |
| pour | 21.2 | 0.4 |
| fabric | 18.9 | -1.5 |
| wheel | 29.1 | 2.5 |

These are "a different take" numbers, in the same range as the text-window milestone (17-27 dB), not
"slightly noisier copy" numbers. The cause is the same: the bf16 sampler amplifies any last-digit change.

## Run 2: the shared graph pool, checked against today's references

Two cards, two sampler workers, batch 1, `LTX_SAMPLER_SHARED_POOL=1` (run `two-way-w2-b1-p1`). This changes
no arithmetic, so it is held to the existing references.

| Arm | Checked against | Clips checked | Exact | Seconds per clip (mean) |
| --- | --- | ---: | ---: | ---: |
| placement probe | today's references (`w93c`) | 10 | 10 | 1.360 |
| timed, 120 prompts | today's references (`w93c`) | 116 | 116 | **1.348** |

- **Byte-exact, and the best exact figure so far** (1.358 with private pools on packet 95).
- **A sampler worker now costs 0.27 / 0.23 GiB of video memory on the two sampler cards, instead of
  2.76 / 3.00 GiB.** Free at the freeze: 7.5 / 10.1 / 11.8 / 14.7 GiB (2.65 / 4.78 with private pools).
- The whole-chain replay check (every block graph of a card replayed in sequence, compared bit for bit with
  the eager chain, order A, B, A, B over the two stage shapes) passed before the freeze.
- The measurement is stored as `data/batch-96/two-way-w2-b1-p1/pool-calibration.json` and is what admits
  the larger pooled runs.

## Run 3: two batch-2 jobs in flight (four clips), shared pool: 1.122 s per clip

Two cards, two sampler workers, batch 2, shared pool (run `two-way-w2-b2-p1`), admitted on the measured pool
cost from run 2.

| Arm | Checked against | Clips checked | Exact | Seconds per clip (mean) | Sampler job (2 clips) | Compute seconds per clip, cards 0-3 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| proof: other neighbours | batch-2 references (from run 1) | 10 | 10 | – | 2.64 s | 0.74 / 1.01 / 0.26 / 0.58 |
| proof: swapped slots | batch-2 references | 10 | 10 | – | 2.66 s | 0.57 / 0.81 / 0.26 / 0.55 |
| timed, 120 prompts | batch-2 references | 113 | 113 | **1.122** (22.3 fps) | 3.42 s | 0.84 / 1.07 / 0.37 / 0.72 |

- **1.122 s per clip, every clip byte-identical to its batch-2 reference.** The references were made in run 1
  by a different server with private pools; this server reproduced them with the shared pool, other pairings
  and two jobs in flight.
- Card 1 is now the limit: 1.07 compute-seconds per clip at a 1.12 s stream is 95 % busy. It carries 25
  transformer blocks and one of the two decode workers. Card 2 is busy a third of the time.
- Total compute per clip is 2.99 GPU-seconds. Spread evenly over four cards that would be 0.75 s per clip, so
  the remaining gap to 1.042 s is placement, not work.
- Free video memory at the freeze: 7.1 / 9.9 / 11.8 / 14.7 GiB.

## Run 4: batch 4 (one job, four clips), shared pool: proven the same way, 1.209 s per clip

Two cards, one sampler worker, batch 4, shared pool (run `two-way-w1-b4-p1`). This run made the batch-4
references (`stability-01-b4-*`).

| Arm | Checked against | Clips checked | Exact | Seconds per clip (mean) | Sampler job (4 clips) | Compute seconds per clip, cards 0-3 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| reference (makes `stability-01-b4-*`; two fixtures generated twice in other slots, byte-identical) | – | – | – | – | 4.42 s | 0.64 / 1.05 / 0.35 / 0.68 |
| proof: other neighbours | batch-4 references | 12 | 12 | – | 4.42 s | 0.66 / 1.05 / 0.35 / 0.68 |
| proof: rotated slots | batch-4 references | 12 | 12 | – | 4.42 s | 0.56 / 0.94 / 0.35 / 0.68 |
| timed, 120 prompts | batch-4 references | 111 | 111 | **1.209** | 4.64 s | 0.63 / 0.97 / 0.37 / 0.69 |

- **Batch 4 is row-independent in the real server too:** 135 of 135 clips byte-identical to their batch-4
  references with other neighbours, other slots and changing groupings.
- One job at a time gives 1.16 s per clip from the sampler alone (4.64 s for four clips), so this run could not
  beat two batch-2 jobs. Compute per clip fell again, to 2.66 GPU-seconds.
- The sampler job costs 2.6 s for two clips and 4.4 s for four: the saving per added clip shrinks, because the
  work that scales with clips (the 1024-token text context of each clip) now dominates the weight reads.
- Picture PSNR of the batch-4 references against today's references: 17.9-29.5 dB (boat 17.9, marble 25.2,
  bird 18.1, pendulum 21.7, rain 24.2, paper 20.5, candle 21.8, pour 18.0, fabric 18.8, wheel 29.5). A
  different take again, the same range as batch 2 and as the text window.
- Card 1 (25 blocks plus a decode worker) is the busiest card in every batch run, at 0.97-1.07 s per clip.

### Two batch-4 jobs: the first capture job failed, cause not yet known

Run `two-way-w2-b4-p1` (23:00 UTC) stopped cleanly with exit 6: worker 0's pinned capture job ended without
its done marker and without capturing a graph. No GPU fault, no refusal receipt, and the server log has no
traceback: a failed pipeline job keeps its error in memory until a prompt waits for it, and the capture prompt
does not wait. The same step passes with one worker at batch 4 and with two workers at batch 2. To do: read
the stored error from a live reproduction, and make failed jobs write their error to the run directory.

## Run 5: two batch-2 jobs on the four-card layout: 1.053 s per clip (23.7 fps)

Blocks spread 18/18/8/4 over the four cards (`shard4-a`), two sampler workers, batch 2, shared pool (run
`shard4-a-w2-b2-p1`, 2026-10-05 00:00 UTC).

| Arm | Checked against | Clips checked | Exact | Seconds per clip (mean) | Sampler job (2 clips) | Compute seconds per clip, cards 0-3 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| proof: other neighbours | batch-2 references (run 1) | 10 | 10 | – | 2.78 s | 0.61 / 0.73 / 0.45 / 0.64 |
| proof: swapped slots | batch-2 references | 10 | 10 | – | 2.78 s | 0.60 / 0.72 / 0.45 / 0.65 |
| timed, 120 prompts | batch-2 references | 113 | 113 | **1.053** (23.7 fps) | 4.15 s | 0.89 / 0.92 / 0.64 / 0.88 |

- **1.053 s per clip against a target of 1.042 s: 1.1 % short of 24 fps**, every clip byte-identical to the
  batch-2 references that a two-card server made in run 1. A different block layout on other cards reproduces
  the same bytes.
- The load is now even: all four cards 61-88 % busy, none saturated. The sampler sets the pace: two jobs of
  4.15 s each give four clips per 4.15 s.
- The spread costs more total work (3.33 GPU-seconds per clip against 2.99 on two cards) but uses the idle
  cards.
- Free video memory at the freeze: 10.8 / 15.1 / 5.3 / 11.1 GiB.

## What this means for 24 fps

With one batch-2 job the two sampler cards have room. Two jobs in flight (four clips) should bring the stream
to roughly the busiest card's compute per clip (card 1: 1.06 s, which includes its share of decode). Batch 4
reads the weights once per four clips and should go lower, at which point decode (two workers) becomes the
limit. Both need more video memory than private graph pools leave, which is what the shared-pool option is for.
Results of those runs are appended below.
