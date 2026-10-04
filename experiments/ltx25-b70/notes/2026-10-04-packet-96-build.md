# Packet 96: one sampler job for two or four clips (build, 2026-10-04)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.
No GPU was used. Background: [95 build](2026-10-04-packet-95-build.md), the batch
row-independence probe (`scripts/probe-batch-row-independence.py`, results in
`/home/steve/b70-host-diagnostics/batch-probe/batch-row-independence-01.json` and
`-02-all.json`), and design A of [two-clip-sampler-design.md](two-clip-sampler-design.md).

## In plain words

Today every clip gets its own transformer passes, and each pass spends most of its
time reading 42 GB of weights. This packet lets one pass serve two or four clips at
once, so the weights are read once for all of them. It is chosen per server at
launch (`LTX_SAMPLER_BATCH` = 1, 2 or 4; 1 is today's setup, unchanged).

A batched clip is the same mathematics with slightly different rounding (the probe
measured about 0.1 % of the output's size), so it cannot match today's references.
That makes adopting it the owner's decision. What this packet does is make the
measurement possible and prove, in the real server, that at a fixed batch size a
clip's bytes depend only on its own prompt and seed: not on which clips share its
batch and not on which slot it sits in. The runner makes new references for batch 2
or 4, then regenerates every fixture with different neighbours and different slots
and requires every clip to match byte for byte. It also reports how close the batched
clips are to today's references (picture and sound), as a "different take" figure,
not a gate.

## Design

- **Option:** `LTX_SAMPLER_BATCH`, read once at import by the sampler node (allowlist
  1/2/4; 3 is refused at import because batch 3 failed the probe's slot and
  identical-row tests). Recorded in the sampler, freeze, pin and coverage receipts
  (`sampler_batch`; freeze and coverage also record the batch of every captured
  sampler signature). `LTX_SAMPLER_WORKERS` gains 1 (one sampler job in flight).
- **One job carries B consecutive clips** (`ltx_sampler_batch.Grouper`, used by
  `LTXPipelineSampler._batch_step`). Each prompt deposits its own clip. The prompt
  that completes a group of B submits the whole group as one sampler job, which runs
  the sealed chain once at batch B: stage-1 sampling, latent upsample, stage-2
  sampling (`pipeline_sampler_node.sample_batch`). The result is split into B
  batch-1 latents (cloned), each with its own worker-side sentry, done marker,
  context sentry and fingerprints, and handed to decode exactly as a single clip's.
  Decode is untouched.
- **Emission:** prompt i still emits exactly one clip, clip i - depth, in clip order
  (each prompt waits for the specific job holding its clip, so jobs finishing out of
  order cannot reorder clips). Timed depth = (W+1)·B - 1: W jobs running plus one
  queued, the same rule as packet 95 (B = 1 gives depth W). Serial depth = B - 1: the
  prompt that completes a group waits for that group's own job, so jobs run strictly
  one at a time (capture, reference and proof arms). Depths above packet 95's limit
  of 4 are admitted only on batch servers (`MAX_BATCH_DEPTH` = 24).
- **Fixed batch shape:** a job always has B rows. When a stream ends (the client sets
  `stream_last` on its last prompt) the open group is submitted with its missing rows
  repeating the last real clip's inputs; those rows are computed and discarded. The
  capture-pass prompt is one real clip plus B - 1 such rows. A batch server never runs
  any other batch size: batch-1 sampler graphs are never captured there, the
  prompt-thread ('original') sampler is refused, an arm built for another batch is
  refused, and the freeze requires every captured sampler signature to be batch B.
- **Decode order:** a job's B latents are emitted by B consecutive prompts in clip
  order, and the unchanged replica decode picks its card by clip-index parity, so
  the B latents alternate between the two decode workers in clip order. The decode
  receipt's queue length is recorded per prompt (`decode_pending` in the client rows,
  median and maximum in the summary).
- **Encode lookahead stays at 2** (two encode workers). A batch job can only start
  when the prompt holding its last clip runs, and that prompt already has its own
  conditioning, so encoding further ahead would not start any job earlier. What the
  encoder must do is have the next prompt's conditioning ready: a window encode
  takes about 0.56 s on one of two workers (about 0.28 s per clip of capacity),
  against a target stream interval of about 0.9 s that the two decode workers set
  (0.9-1.0 s per clip). It keeps up.
- **New arms** (generator `SAMPLER_DEPTH_OVERRIDES_96`, `SAMPLER_BATCH_ARMS`; the gate
  checks the depth formula): `pipe-samp2-tsh-rep-wlean-s1` (batch 1, one worker),
  and for B in 2, 4: `pipe-samp2-tsh-win-b<B>` (capture pass, decode on xpu:3,
  depth B-1), `pipe-samp2-tsh-rep-wlean-b<B>-ref` (reference and proof arms, depth
  B-1), `pipe-samp2-tsh-rep-wlean-b<B>-w<W>` for W = 1..4 (timed, depth (W+1)B-1). The
  batch arms' sampler node also carries `batch` (the batch it was built for) and
  `stream_last`; batch-1 graphs do not have them and are byte-identical to packet 95's.

## Exactness conditions and how each is enforced

| Condition | Enforced | Proven offline (test-packet96-batch-cpu.py) |
| --- | --- | --- |
| Initial noise per clip, never one batch draw | `BatchNoise`: each clip's own Noise object draws for a batch-1 latent of its shapes (prepare_noise seeds the global generator with that clip's seed), rows concatenated, all B draws under the process noise lock | rows equal the real `Noise_RandomNoise` batch-1 draws of seeds 42/17/123/808; one batch draw differs |
| Ancestral per-step noise per clip | `batched_ksampler`: one generator per clip, built by the stock `default_noise_sampler` on a batch-1 view (same seed rule), concatenated per step; only euler_ancestral admitted; the sampler seed must be row 0's | rows equal the batch-1 generator sequence for each seed over three steps |
| Conditioning per clip | Raw text features have a per-prompt token count (`lt.py`: `out[:, :, -sum(attention_mask):]`), so they cannot be stacked. The batch cond carries a placeholder naming a per-job list of each clip's own raw tensor. Inside the stock `extra_conds` call the connector shadow converts each clip's raw tensor exactly as `extra_conds` converts it and runs the connector at batch 1 per clip, then stacks the fixed 1024-token outputs. Lean memo per clip (row) only, never across rows. Every other cond field must be equal between clips, except `pooled_output`, which LTXAV never reads | stand-in connector called once per clip on its own [1, N, D] tensor (N = 56 and 31), outputs stacked, reused per row for stage b; unequal metadata, a per-clip mask, a width mismatch and different patchers refuse |
| Every batch-carrying argument stacked | ComfyUI's own batch path (one cond chunk of B rows: x, timesteps, context, option sigmas, a_timestep all batch B). A guard on every forward refuses any tensor argument without the batch dimension (only the sigma schedule is unbatched) | packet 72's batchproof census: the real `_stack_rows`/`_double_batch_lists` and the expected census agree; the guard accepts it and refuses the unstacked census and an unstacked mask |
| Lockstep (same sigma on every row) | the clips' sigma schedules must be bitwise equal; on the first forward of each stage the timesteps and option sigmas must be equal on every row (`a_timestep_scaled.max()` mixes rows) | unequal schedules and unequal timestep rows refuse |
| The batch-wide latent-shift decision | `inner_sample` shifts the latent only if the whole batch is non-zero; every row must agree | mixed rows refuse |
| Fixed shape, fill discarded | `Grouper`; fill rows are never emitted | flush with fills, discard, refusals of non-consecutive or reused indices and changed signatures |
| Fail closed | every check raises `BatchRefused` with the reason; a refused job writes `sampler-batch-refused-<job>-<ms>.json` and the failure latches like any sampler failure | - |

Not proven offline: that a batch-B forward of the full model, with graph capture,
the batched upsampler and both stages, gives row bytes independent of neighbours and
slot. That is what the proof arms test in the server.

## References and the proof (B = 2, 4)

- **Prompt counts:** prompt i emits clip i - sampler depth - decode depth (decode
  trails the sampler by two clips on the replica arms). The reference and proof arms
  must emit K clips (K = 10 for B = 2, 12 for B = 4), so they run K + (B - 1) + 2
  prompts: **13 for B = 2, 17 for B = 4**. The runner reads both depths from the
  packet's own arm graph. The timed arm's 120 prompts emit 120 - depth - 2 clips
  (B = 2: 115 with W = 1, 113 with W = 2). The self-check runs depth + 4 prompts
  (two emitted clips). Every arm must emit exactly clips 0..K-1 in prompt order; a gap
  or a duplicate fails it (client exit 12, proof checker rejection).
- **Reference arm** (only if `data/stability-01-batch<B>-prereg.json` does not exist):
  the ten fixtures in order `ref`, one job at a time, not compared.
  B = 2: pairs (0,1)(2,3)...(8,9). B = 4: (0,1,2,3)(4,5,6,7)(8,9,0,1), so fixtures 0
  and 1 also appear a second time in other slots with other neighbours.
  `make-batch-oracle-96.py` refuses unless every fixture was emitted from a batch-B
  job of this server and packet, the window encoder was used, the tensors re-hash,
  and the repeated fixtures are byte-identical. It then copies the first clip of each
  fixture to `stability-01-b<B>-<fixture>` (same store and format as the w93c set)
  and writes the prereg with each reference's arrangement (job, slot, neighbours).
- **Proof arms** (same arm): `proof-neighbours` (B = 2: (0,3)(2,5)(4,7)(6,9)(8,1),
  same slots, other neighbours; B = 4: (0,5,2,7)(4,9,6,1)(8,3,0,5)) and `proof-slots`
  (B = 2: (1,0)(3,2)..., same neighbours, swapped slots; B = 4: rotation by one, every
  fixture in another slot). Every clip must be byte-identical to its `b<B>` reference
  on all four raw outputs, and `check-batch-proof-96.py` checks from the receipts that
  every clip really had other neighbours (or another slot) than in the reference arm.
- **Timed arm:** 120 prompts in the `shift` order (cycle k rotated by k, so batch
  composition changes every cycle), every clip checked against the `b<B>` references.
- **Closeness report:** `batch<B>-reference-vs-w93c.json`, per fixture: picture PSNR,
  waveform SNR and PSNR, latent differences against the w93c reference. Not a gate.
- The summary names the reference set every arm was checked against (`references`
  column; `b<B>` for proof and timed arms, `window` = w93c for the batch-1 control).

## Memory

Graph memory per sampler worker is assumed to grow linearly with the batch: 0.12 GiB
per block at batch 1 (94f/95b), so 0.24 and 0.48 at batch 2 and 4, plus glue on
xpu:0. That is an upper bound until the first batch run measures it. Free memory at
the freeze with no sampler worker is taken from the 95b receipts (two-way:
8.17/10.78/11.84/14.55 GiB; shard4-a: 11.85/15.75/5.82/11.57 GiB).

| Layout | W | B | Predicted free at freeze, GiB (xpu:0/1/2/3) | Runner |
| --- | ---: | ---: | --- | --- |
| two-way | 1 | 2 | 2.45 / 4.78 / 11.84 / 14.55 | runs (xpu:0 tight) |
| two-way | 2 | 2 | -3.27 / -1.22 / 11.84 / 14.55 | worker 1 skipped (exit 18, live check) |
| two-way | 1 | 4 | -3.27 / -1.22 / 11.84 / 14.55 | skipped before capture (exit 18) |
| shard4-a | 1 | 2 | 7.33 / 11.43 / 3.90 / 10.61 | runs |
| shard4-a | 2 | 2 | 2.81 / 7.11 / 1.98 / 9.65 | worker 1 skipped by 0.02 GiB on xpu:2 |
| shard4-a | 1 | 4 | 2.81 / 7.11 / 1.98 / 9.65 | skipped before capture by 0.02 GiB on xpu:2 |
| shard3-c | 1 | 2 | 5.52 / 9.79 / 4.04 / 14.90 | runs |

The first worker's capture cannot be checked live: the transformer is only loaded by
that capture (the 95b cap0 receipt shows 0 bytes on xpu:0 before it). So a batch
server first runs `worker-headroom-96.py plan`, and skips the combination before any
capture if one worker's batch-B graphs are predicted to break the 2 GiB floor (an
over-committed capture is not allowed to happen). Later workers get the live check
(floor + estimate + the decode replica and VAE room still to come). The freeze still
enforces the 2 GiB floor (exit 16). The upsampler's own load call asks for about
24 MB per clip, far below the 1.2 GiB the frozen loader already requires.

**Recalibrate after the first batch-2 run:** two-way W1 B2's coverage receipt
`sampler-capture-coverage-f96-twowayw1b2-cover.json` gives xpu:0's free memory with
one batch-2 worker. Per-block cost at batch 2 = (8.17 - free_xpu0 - 0.2) / 23.
Put it into `PER_BLOCK_GIB` in `scripts/worker-headroom-96.py` (outside the packet; no
rebuild) before deciding on shard4-a W2 B2 or any B = 4 launch.

## Runner, per server: `scripts/run-campaign-96.sh <layout> <W> <B>`

Same safety machinery as 95b (health-receipt admission recorded, SIGINT check,
proven-quiescence stop, stall handling, traps, sync points, receipt commits with
explicit paths, exit codes; requires and records `NEOReadDebugKeys=1
EnableDeferBacking=0`, `LTX_SAMPLER_BATCH`, workers and placement from the server's
environment). Batch-aware done-marker check (`missing-markers-96.py`).

text-window probe → (B > 1) memory plan → serial capture pass (pin worker k, one
prompt alone; live headroom check before worker k ≥ 1 at B > 1, k ≥ 2 at B = 1) →
coverage (all workers, batch-B signatures only) → decode probe → freeze → self-check
(depth + 4 prompts of the timed arm, two emitted clips; at B = 1 W + 4 as in 95) → B = 1: placement probe
(13 prompts) and timed arm against w93c, the packet 95 path → B > 1: reference arm
(or verify the `b<B>` references exist) → proof arms → timed arm (120 prompts) →
summary → graceful stop. Output `data/batch-96/<layout>-w<W>-b<B>`, run names
`encoder-server-batch-96-<layout>-w<W>-b<B>`. New helper copies with a 96 name
(the live 95b run's files are untouched): `run-throughput-fixtures-96.py` (fixture
orders, stream_last, batch arrangement per row, `--no-oracle`), `missing-markers-96.py`,
`summarize-campaign-96.py`, `worker-headroom-96.py`, plus `make-batch-oracle-96.py`
and `check-batch-proof-96.py`.

The summary keeps 95's per-arm columns (clips verified/exact, interval median and
mean, encode/sampler/decode job medians, clips in flight, compute-engine busy seconds
per clip per card) and adds the reference set, sampler job seconds per batch job and
per clip (job / B), batch jobs in flight, and the decode queue depth.

## Index bases

264000 + 1000 × (12 × layout + 3 × (W - 1) + batch index); layout two-way / shard4-a /
shard3-c = 0 / 1 / 2, batch 1 / 2 / 4 = 0 / 1 / 2. Capture pass base + 10k,
self-check +100, probe or reference +200, proof-neighbours +300, proof-slots +400,
timed +500 (to +619). All 36 combinations are disjoint and above every 95b index.

| Combination | Base |
| --- | ---: |
| two-way W1 B1 / B2 / B4 | 264000 / 265000 / 266000 |
| two-way W2 B1 (control vs w93c) / B2 / B4 | 267000 / 268000 / 269000 |
| shard4-a W1 B1 / B2 / B4 | 276000 / 277000 / 278000 |
| shard4-a W2 B1 / B2 / B4 | 279000 / 280000 / 281000 |
| shard3-c W1 B2 | 289000 |

## Packet and gate

- `R/prepared-encoder-batch-96`, manifest
  `5822b050bdf5784ab62cc14e0b69f8c9612af26963e23b61605edd554eba049f`. The generator
  adds `source/scripts/ltx_sampler_batch.py` (in the extension inventory), the 13 new
  arm graphs and a `sampler_batch` manifest section; the gate checks the batch arms'
  depths against the formula and their two extra inputs, and every packet 95 graph is
  byte-identical in the new packet.
- Gate (`--check-only`, 2026-10-04 21:30 UTC, fourth build): rc 0 for
  `encoder-server-batch-96-{two-way-w1-b2, two-way-w2-b1-p1, two-way-w2-b2-p1,
  two-way-w1-b4-p1, two-way-w2-b4-p1, two-way-w2-b2, shard4-a-w1-b2, shard4-a-w2-b2-p1,
  two-way-w2-b1}`, without a receipt and with
  `data/health/four-card-health-20261004T2042Z.json`.
- CPU tests: `test-packet96-batch-cpu.py` 17/17 (both reviews, the shared pool and the pool
  calibration). The calibration lives outside the packet (runner and headroom tool only),
  so the manifest is unchanged. (grouping with workers 1-4 and batches
  2/4, fill and refusals, per-clip noise, packet 72 census, per-clip connector,
  env allowlist, lockstep, batch 1 unchanged, agreement of generator/gate/runner/
  client/packet, proof arrangements, memory and markers). Packet 90c-95 tests pass.
  Full lane sweep after the third build (114 test files before, 115 after): 68 pass, the same 47 old
  failures; no other test changed result (before this build: 67 pass, 47 fail).

## Launch (one server per combination; wait for each runner to stop its server)

Planned order: (1) two-way W1 B2, pool off: the smallest batch proof. (2) two-way W2 B1 p1
(`1` as the 4th runner argument, `LTX_SAMPLER_SHARED_POOL=1`): the exactness gate for the
pool change against the w93c references, and the pool calibration. (3) two-way W2 B2 p1.
(4) two-way W1 B4 p1, then W2 B4 p1. Runs 3 and 4 are admitted on the calibration from (2);
if it shows they do not fit, they stop cleanly (exit 18).

```
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-batch-96
M=5822b050bdf5784ab62cc14e0b69f8c9612af26963e23b61605edd554eba049f
L=two-way W=1 B=2      # then: shard4-a 1 2; after recalibration: shard4-a 2 2, shard4-a 1 4
SP=0 SUF=                # pooled runs: SP=1 SUF=-p1
nohup env --default-signal=INT NEOReadDebugKeys=1 EnableDeferBacking=0 LTX_BUSY_WINDOWS=0 LTX_SAMPLER_PLACEMENT=$L LTX_SAMPLER_WORKERS=$W LTX_SAMPLER_BATCH=$B LTX_SAMPLER_SHARED_POOL=$SP /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 $M --run-name encoder-server-batch-96-$L-w$W-b$B$SUF --health-receipt <fresh receipt> > $R/encoder-server-batch-96-$L-w$W-b$B$SUF.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-96.sh $L $W $B $SP > $R/campaign-96-$L-w$W-b$B$SUF.log 2>&1 &
```

Batch-1 control on the same packet: `L=two-way W=2 B=1` (checked against w93c).

## Shared graph pool (`LTX_SAMPLER_SHARED_POOL`, added in the third build)

In plain words: today every sampler block graph keeps its own private scratch memory,
which costs about 0.12 GiB per block per sampler worker. With this option on, all of
one worker's block graphs on one card share a single scratch pool, the way the text
encoder already does. That should cut a worker's graph memory to roughly one block's
worth per card. It changes no arithmetic, only where scratch memory lives. Exactness
is still checked against the references.

- Option read once at import by `ltx_graph_capture` (allowlist 0/1, default 0). With 0
  the capture is the packet 95 call unchanged: no `pool=` and a fresh stream per graph.
  Recorded in the capture summary (`shared_pool`), coverage, freeze and sampler
  receipts (`sampler_shared_pool`), and the manifest (`sampler_shared_pool`, gated).
- With 1: one `torch.xpu.graph_pool_handle()` and one capture stream per (card,
  thread), passed as `pool=`/`stream=`, capture under the card's device context. This
  copies `ltx_graph_text_encoder.py` lines 41-90 and 223-235. Handles are dropped at
  `install()` and `restore()` (the stale-handle INTERNAL ASSERT, `ltx_graph_text_encoder.py`
  414-418 and 450-452).
- Outputs stay outside the pool. Block outputs are the slot's static buffers, asserted
  in place. A capture that leaves any new tensor cached on a block module (parameters,
  buffers, plain tensor attributes) is refused under the pool.
- **Chain check before the freeze, with the pool on or off (same receipt):** every route on
  a card must hold both stage signatures for every worker (a missing one rejects). The
  card's whole graph chain is replayed on seeded inputs in clip order, A, B, A, B, and
  every replay must equal its eager chain and its repeat, bitwise. Slot contents are
  restored afterwards. A mismatch refuses the freeze (`chain-check-failed`, exit 16).
  The check's peak is budgeted first: snapshots, inputs and outputs from
  `chain_check_budget`, plus 0.25 GiB x batch of eager scratch and a 0.5 GiB margin. If it
  does not fit, the freeze is refused (`chain-check-no-room`). Afterwards the check's
  memory is released (`empty_cache`), and the 2 GiB floor and the resident set are judged
  on a fresh reading.
- A reset graph (failed, inert or refused capture) that was its pool's only owner retires
  the pool handle, so a retry captures into a fresh pool.
- Memory (second review): no guessed constant protects a capture. The first worker, pooled
  or not, is admitted on the private-pool bound (0.12 GiB per block at batch 1, linear in
  the batch, plus glue), because a shared pool cannot need more than private pools. Worker 1
  is checked live on the same bound: no reading exists between the model load and worker
  0's capture. Every later worker (k >= 2) is charged the measured cost of worker k-1 on
  each card (its own room receipt minus this one) x 1.25 + 0.25 GiB. The headroom receipt
  records the bound, the measurement and which one was used.
- **Calibration from an earlier run of the same packet.** Every pooled run with two or more
  workers writes `data/batch-96/<layout>-w<W>-b<B>-p1/pool-calibration.json` after its
  coverage check (schema `ltx.pool-calibration-96.v1`: `packet_manifest_sha256`, `layout`,
  `batch`, `shared_pool` 1, `worker`, `per_card_gib`, the two source receipts,
  `written_unix`). `per_card_gib` is the last worker's measured pooled cost per card: free
  memory at its room receipt (just before its capture) minus free memory at the coverage
  receipt (just after). A later pooled run of the SAME manifest and layout uses it when it
  has no in-run measurement: in the plan check before worker 0, and for worker 1. It picks
  the largest calibration batch not above its own (then the most recent) and charges
  measured × (batch / calibration batch) × 1.25 + 0.25 GiB per card holding blocks. With no
  matching receipt (other manifest, other layout, pool off, larger batch, none at all) it
  falls back to the private-pool bound. The headroom receipt's `basis` names the bound, the
  in-run measurement, or the calibration file; `calibration_considered` lists what was
  refused and why. For worker 0 this assumes its pooled cost does not exceed the calibrated
  worker's by more than the margin. That is an assumption, and the floor re-measured after
  the chain check at the freeze is the backstop.
- The first pooled run, two-way W2 B1 p1, admits worker 1 on the private-pool bound (it
  fits: today's shape) and writes the calibration that the batch-2 and batch-4 pooled runs
  then use.
- Pool off is not byte-for-byte packet 95's lifecycle: the capture calls are the same, but
  two read-only checks were added (the module-tensor census around each capture and the
  chain check before the freeze).
- Runner: 4th argument `0|1` (default 0), which must match the server's
  `LTX_SAMPLER_SHARED_POOL`. Pooled runs are named `encoder-server-batch-96-<layout>-w<W>-b<B>-p1`,
  write to `data/batch-96/<...>-p1`, and use index bases 300000 + 1000 × (the same IDX).

Lines changed in `ltx_graph_capture.py` (new numbering; everything else is packet 95's
text): 482-643 (inserted after `class Entry`: option, pool/stream helpers,
`_module_tensors`, `chain_check`); 1042-1060 (capture site: `capture_resources`, pooled
branch under the device context); 1073-1083 (refuse a cached tensor under the pool);
1282 (`shared_pool` in the summary); 1381 (`clear_shared_pools()` in `install`); 1573
(the same in `restore`). The block sits after `class Entry` because
`test-ltx-graph-capture-stdlib.py` executes the module text between `SCALARS` and
`class Entry` on its own.

## Second review fixed (2026-10-04, fourth build)

1. The freeze re-measures memory and residency after the chain check and judges the floor
   on that reading; the check's peak is budgeted first.
2. Pooled admission uses the private-pool bound, then measured worker costs (see Memory).
3. The client's leftover `fill` name (a NameError on the first compared clip) is fixed. An
   end-to-end CPU case now runs the real client against a stand-in server for batch-1,
   reference, proof and timed arms. `ruff` (F821/F822/F823/F841/F811/F632) passes on every
   new or changed 96 script.
4. The runner requests the reference arm in the summary only when it ran
   (`summary_args`); a test covers the second run.
5. The inert-capture retry retires an unowned pool handle.
6. The chain check requires both stage signatures on every route and replays A, B, A, B.

## Review findings fixed (2026-10-04, second build)

An independent review found seven defects; all were confirmed in the code and fixed.
The packet was rebuilt in place (never launched).

1. **Batch provenance on the wrong clip.** The client read the emitting prompt's own
   sampler receipt, but decode trails the sampler by two clips. Now every arm's sampler
   receipts are joined by the clip's absolute index, and `batch.rows[slot]` must equal
   that index. The summary's context hashes are attributed the same way.
2. **A rejected timed proof was ignored.** The runner now fails the campaign (exit 19).
   The summary requires passing proof receipts (`--require-proof`) for batch runs.
3. **Prompt counts omitted decode's two-prompt drain** (11 and 15 would have emitted 8
   and 10 clips). Now 13 and 17, derived from the arm graphs' depths. The reference
   maker requires the complete `ref` emission sequence, including B = 4's two repeats.
4. **The proof accepted empty, short or duplicated arms**, and the client excluded
   duplicates as fills. Both now require exactly clips 0..K-1 in order, each once,
   each the fixture of the arm's order.
5. **`leading_dims` skipped the video tensor** of `[video, audio]` (the first child of
   an untagged payload tuple). It now traverses every child; tested through the real
   `describe()`.
6. **An absent arm or pair made the summary pass.** It now exits 3.
7. **Receipt commits could carry other staged changes.** The 96 runner commits only
   its explicit paths (`git commit ... -- <paths>`).

New CPU tests run real batch-step and decode lag simulations. They check provenance
per emitted clip, emission counts including the drain, and the checker's rejection of
missing, duplicated, empty and miscounted arms.

## Decided differently from the brief

- `cond_or_uncond` and `uuids` are not doubled. ComfyUI's own batch path runs one
  cond chunk of B rows, so those lists stay length 1 (they are per chunk and the LTX
  model never reads them). The batchproof stacker had to double them because it glued
  two chunks together. Every tensor field is batch B, checked on every forward.
- The connector cannot run on stacked raw features (they differ in token count), and
  the stock path insists on running it inside `extra_conds`. So the batch cond carries
  a placeholder and the connector runs per clip inside that call, as described above.
- Encode lookahead is unchanged at 2 (reason above).
- "One job at a time" for the reference arm is the serial depth B - 1; the proof arms
  use the same arm, so neither depends on concurrency. The timed arm runs W jobs.
- The batch self-check is not compared (the batch references may not exist yet); it
  only proves the timed path runs without refusals, as 95's check does.
- On a batch server a clip index is never accepted twice (stricter than batch 1).

## Unverified offline

- Whether the full model at batch B, with graph capture, the batched latent upsampler
  and both stages, gives row bytes independent of neighbours and slot. The probe
  covered 12-16 eager blocks; the upsampler's row independence was never probed.
  The proof arms decide.
- The batch-B graph memory: linear in the batch is an upper bound. two-way W1 B2 is
  predicted at 2.45 GiB free on xpu:0 at the freeze, close to the floor.
- Whether ComfyUI's sampler path, the forward guard and the placeholder cond behave
  as traced in the source; nothing here ran through the real executor, the real
  model or a real card. The guard fails closed with a receipt if they do not.
- The shared pool on real XPU graphs: whether `torch.xpu.graph(pool=...)` aliases
  transients across the 48 block graphs and both stage shapes as it does for the text
  encoder, whether any block op allocates memory that persists across replays without a
  module attribute (the cache check cannot see that; the chain check would), and the
  real per-card cost (0.6 GiB is a guess).
- Speed: how much one pass costs at batch 2 and 4, and whether decode (about 0.9-1.0 s
  per clip with two workers) caps the stream before the sampler does.
