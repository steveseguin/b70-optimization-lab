# Two clips per sampler pass: the two designs the batch proof chooses between

*2026-09-17. Standing position 2.03 s per distinct clip, exact, with the
captured block region at 1.57 s of that. The blocks are weight-read bound
(0.74 s floor), so the only large exact lever left is to make each weight
read serve two clips.*

## A. Pair sampler (if a batch-2 forward is bitwise equal to two batch-1 forwards)

Prompt N samples clips N and N+1 as one batch of two and emits clip N; clip
N+1's sampled latent is parked and emitted by prompt N+1, which samples
nothing (or samples N+2 and N+3 if the stream is long). Every prompt still
emits exactly one clip, so the existing per-clip oracle against the fixture
references applies unchanged, and the pipeline's decode-behind and encode-
ahead stages are untouched.

Inputs for clip N+1 come from the queued next prompt, exactly as encode-ahead
already reads its text: its prompt text (encode-ahead computes the
conditioning) and its two `noise_seed` values. Nothing is guessed; if the
next prompt is not queued, the prompt samples alone at batch 1.

Exactness conditions, each provable per shape on the resident model:

1. Block forward: batch-2 rows equal batch-1 rows (the packet 70 proof).
2. Initial noise: `prepare_noise(latent, seed)` per clip, first draw of its
   own seed, concatenated; never a batch-2 draw from one seed.
3. Ancestral per-step noise: a custom `noise_sampler` that draws each clip's
   half from its own `torch.Generator` seeded as `default_noise_sampler`
   would for a batch-1 clip, concatenated.
4. Conditioning: one cond whose `cross_attn` is `cat(cond_N, cond_N+1)`;
   `repeat_to_batch_size` leaves a tensor whose leading dimension already
   equals the batch untouched.
5. Latent upsampler and stage-B sampler on the batch-2 latent: the same
   row-equality property, checked by the same proof machinery on the
   upsampler's forward.
6. Decode: split the batch into two batch-1 latents and decode each with the
   sealed decoder, so the decoder needs no proof.

Cost model: block region per pass grows from 1.57 s toward the compute-bound
part only (weights read once for both rows); packet 29 measured 13.8 ms of
token-dependent work per 64-token forward against 118 ms of weight reads,
so a pair pass should cost roughly 1.57 + 0.2 s of blocks for two clips,
about 0.9 s of blocks per clip. Expected interval per distinct clip near
1.2 s.

## B. Single-scheduler two-clip sampler (if the proof fails)

One issuing thread owns two clips and both shard cards. Per forward it
issues clip A's xpu:1 segment (blocks 21–47 and the post-glue) and clip B's
xpu:0 segment (pre-glue and blocks 0–20) back to back without waiting, then
waits on events for the two cross-card transfers. Each clip keeps its own
static buffers and captured graphs; no ComfyUI sampler runs on a worker
thread, no registry is shared, and no capture overlaps a replay (both clips'
shapes are captured in a warm-up pass before pipelining starts). This is
not the retired two-thread design. It needs a re-implementation of the
model's forward as two segments calling the same submodules in the same
order, and a two-clip step loop reproducing `sample_euler_ancestral_RF`
with per-clip generators.

Cost model: the two cards work concurrently, so the block region's
throughput cost halves toward 0.8 s per clip; expected interval near 1.2 s
as well, with a heavier build and more ways to be wrong.

Either way, after this lever the remaining distance to 1.042 s is block
kernel work: the audio stream's launch-bound small kernels and the proven
adaLN fusion.

## Probes, 2026-09-17 06:30–06:45 UTC (exclusive cards, block-sized GEMM graphs, all bitwise exact)

| Variant | Speedup vs serial |
| --- | ---: |
| baton hand-off, one issuing thread at a time | 0.997x |
| two free threads, shared default streams, blocking device copies | 1.19x |
| two free threads, per-clip streams, non-blocking device copies with events | 0.996x |
| two free threads, device copies, no device context around xpu:1 replays | 1.28x |
| **two free threads, explicit device contexts, per-clip streams, activation staged device→pinned host→device** | **1.68x** (ideal 1.78x) |

Graph replay and the cross-card copy both return in under 0.1 ms, so the
issuing thread is never the bottleneck; what kills overlap is the driver's
peer copy path and replays issued under the wrong device context. Route A
(batching) is closed by packet 72. Route B is therefore: two worker threads
as in `pipeline_sampler_node`, replay-only once warm (captures taken under
an exclusive lock, replays under a shared one), one stream per clip per
card, and the shard boundary move replaced by pinned-host staging with
events. Evidence: `data/baton-probe/`.
