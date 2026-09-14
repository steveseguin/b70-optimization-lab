# LTX 2.5 north star and execution plan

Written September 13, 2026; sharpened by the user's subsequent start instruction.
The user authorized beginning the work, with small rolling review storage.
[CURRENT.md](../../CURRENT.md) remains
the authority for live state. Measurements and completed experiments belong in
[SPEED-HANDOFF.md](SPEED-HANDOFF.md) and the linked evidence directories.

## North star

**Generate one second of new video in under one second, at 24 fps and a minimum
output resolution of 256x256, on the existing four B70s, without sacrificing
quality or losslessness. Extend it into coherent continuous video with
deterministic replay and bounded memory and disk use.**

Under one second is the actual goal, not a stretch goal. Three seconds is only
an intermediate progress marker. The user expects sustained work over weeks.
The minimum applies to final generated output; preserve the existing two-stage
128-to-256 latent workflow and all its sampling steps. No tiny-resolution
benchmark can satisfy this goal. The current 25-frame clip is 1.042 seconds at
24 fps: completing that whole clip in under one second is a conservative initial
acceptance target. Also report startup and fresh-prompt response separately from
continuing-scene throughput. An acknowledgment, loading animation, repeated old clip or
unfinished denoising preview does not count as generated output.

Success must satisfy speed, quality and stability together. If exact-output
optimization reaches a measured practical limit first, document that limit and
the remaining bottleneck; do not silently lower quality to claim real time.

## Starting point

- Working checkpoint: pinned LTX 2.5 distilled BF16, original 8+3 sampler steps.
- Clip: 256x256, 25 frames at 24 fps, or 1.042 seconds of video, with audio.
- Hardware: four 32 GiB B70s. Transformer on GPU0/1, encoder on GPU2, VAEs on GPU3.
- Warm preview ready: **6.44–7.10 seconds**, after the model is loaded.
  Raw tensors are ready in 6.31–6.95 seconds. First split initialization took
  81.21 seconds to preview and is measured separately.
- Three repeated boat generations and marble/bird references match exactly
  across images, video/audio latents and waveform. Lossless float video/audio
  export passes independent decode verification.
- Rough current capacity: 3.5–3.9 generated frames/second for sequential clips,
  calculated from 25 frames divided by measured warm latency. This is not a
  sustained streaming measurement. Reaching 24 fps requires roughly another
  6–7x improvement at this workload, or a separately validated execution design.
- Text encoder still partially offloads; long-run memory stability and coherent
  continuation across clips are untested. BasicGuider was exact but neutral.

Evidence: [current measurements](data/speed-resident/summary.json).

## What we measure

| Measure | Definition and target |
| --- | --- |
| Fresh-prompt response | Submit a new prompt to the loaded service; time until actual generated output is usable. Report first frame/chunk and complete clip separately. Complete decoded 25-frame target: p95 <1 s, with worst case and all samples visible. <=3 s is an intermediate marker only. |
| Continuous throughput | More than 24 newly generated usable frames per wall second, played at 24 fps. Require p95 <1 s for each new second of video and no playback stalls; averages alone are insufficient. Count overlapping continuation frames only once; exclude repeats, dropped frames and interpolation used to mask slow generation. |
| Playback continuity | No buffer underruns after the declared initial buffer; queue and buffer sizes stay bounded. Report startup buffering and prompt-change delay so batching cannot hide latency. |
| Repeatability | Same pinned model, runtime, configuration, prompt and seed produce identical raw outputs. For streaming, include ordered prompt changes, continuation state and seed schedule in the replay identity. |
| Lossless recording | Save only selected review samples. Decoded lossless review media must match captured samples exactly; a lossy MP4 is only a preview. Persistent recording of the full stream is unnecessary and outside the generation timer. |
| Stability | No device faults, OOMs or unexplained unbounded RAM/VRAM growth during progressively longer tests. A finite test establishes its measured duration, never literal infinity. |

Use fixed, disclosed fixtures and matched timing definitions. Keep fresh prompt
encoding distinct from reuse of an unchanged prompt in a stream. Record median,
p95, worst case, sample count and all failures; label small samples preliminary.
Measure full-clip milestones on at least 30 requests spanning at least 10
prompt/seed fixtures, with no output cache. Keep initialization and compilation
costs visible separately from loaded-service latency.

## Ordered milestones

| Stage | Work | Exit condition |
| --- | --- | --- |
| 0 — Preserve the baseline | Keep current graph, model hashes, runtime identity, exact tensors, timings and failed experiments. | Complete: current result is the rollback/reference point in Git and external evidence storage. |
| 1 — Establish stable operation | Run a bounded sequence on the existing endpoint, mixing original fixtures with additional reference-backed scenes. Observe per-request RAM/VRAM, encoder residency, queue state, latency and faults. | At least 30 completed requests; original fixtures remain exact; allocation growth is explained or fixed before longer operation. |
| 2 — Drive full clips below 1 s | Profile text, denoising, transfers and decode costs; test one justified exact optimization at a time. Use <=3 s as an intermediate marker. | Matched full-suite p95 <1 s at >=256x256, 25 frames/24 fps, and exact output gates pass. Preserve partial wins and the measured remaining gap throughout the campaign. |
| 3 — Build continuous generation | Define continuation inputs/state, deterministic seeds, bounded scheduling, cancellation, prompt changes and incremental display. Establish a reference implementation before optimizing it. | Consecutive chunks form a coherent scene; replay is deterministic; no stale queue growth. Report actual speed even if still below real time. |
| 4 — Sustain faster-than-playback generation | Overlap independent stages where exactness permits, then qualify generation and display with optional review capture. | >24 unique generated frames/s, each second of video ready in p95 <1 s, no playback underruns, bounded memory/queues during a 30-minute run, then a 2-hour run. |
| 5 — Raise resolution and responsiveness | Improve margins below one second, then test higher resolutions one measured configuration at a time. | Each new setting retains its own quality, latency and endurance gates. Keep 256x256 as the minimum and regression baseline. |

Stage3 can begin as CPU/source design work while Stage2 proceeds. Do not wait
for a theoretical proof that every possible speed optimization is exhausted;
advance when the next experiment has a concrete hypothesis and acceptance gate.
Longer endurance runs follow clean shorter tests and a reviewed storage budget.

The first [continuation source audit](notes/continuation-source-boundary.md)
found that the native upsampler removes the frame-preservation mask. A future
reference must define anchoring in both stages, count boundary frames only
once, and resolve audio timing. No continuation graph or quality result is
qualified yet.

## Next optimization questions, in order

1. **Does encoder residency settle?** Its partial CPU offload increased across
   the short campaign. Determine whether this is bounded allocation behavior
   before calling the service ready for sustained use. Do not assume a leak.
2. **Where does the remaining time go?** The latest boat run spent about 1.85 s
   encoding text, 3.58 s in two sampler nodes, and 0.80 s decoding audio/video.
   Existing node events are approximate. Use a bounded diagnostic to separate
   transfer, dispatch and compute only where it will decide the next change.
   Profiled timings cannot replace uninstrumented performance measurements.
3. **Can exact execution use the hardware better?** Investigate encoder
   placement, avoidable copies/allocations and scheduling. A transformer split
   solves memory residency; it does not establish parallel computation of
   sequential layers. Compilation, graph capture or changed kernels remain
   hypotheses until exactness and compatibility are verified.
4. **What can be reused during a continuing scene?** Unchanged prompt encoding
   may be reusable with a complete cache key and invalidation rules. Measure
   that mode separately; it cannot improve the fresh-prompt headline by
   substituting a repeated prompt. Never reuse generated clips as new output.
5. **Can stages overlap without changing results?** Explore encoding the next
   prompt or decoding completed output alongside independent work, subject to
   measured memory headroom. Report effects on first response as well as total
   throughput; a faster batch can still make interactive latency worse.

Prepare any startup-dependent code and CPU tests as durable patches first.
The current loaded extensions are frozen; disk edits do not update them. No
restart is scheduled by this plan. When tested source requires a new runtime,
perform one necessary controlled application reload within the authorized work,
explain that it reloads LTX rather than the computer, and continue optimization.
Do not insert another approval pause for that routine action. Preserve source
identity; do not hot-patch live code or introduce restart/retry chains.

## Quality gates and continuation

Every optimization of the present clip must preserve its checkpoint, native
precision, prompt/seed, dimensions, frame count, sampler and step schedule.
Compare all four tensors byte-for-byte against the corresponding reference,
require finite values and strict deterministic settings, and verify independent
recomputation. A speed result alone cannot pass the quality gate. Keep failures
and neutral results; changes inside observed timing noise are inconclusive.

Continuous video adds context and therefore defines a different workload from
independent text-to-video clips. Give it a separate, pinned reference with exact
continuation inputs and deterministic state transitions. Optimizations must
match that reference. Assess seam continuity, scene/subject persistence and
audio continuity as well: bitwise determinism alone does not prove a coherent
or attractive video. Stitching unrelated clips is not the north-star result.

No lower precision, fewer denoising steps, approximate attention/denoising cache,
smaller output or different checkpoint may be presented as an exact speedup of
the existing baseline. Any future quality tradeoff needs an explicit decision
and a separately labeled target. Lossless encoding means preserving generated
samples; it does not undo distillation or establish equivalence to a dev model.

## Operating and evidence rules

Reuse the existing server after verifying live state. No automatic restart or
retry loops, reboot, driver reset, power-setting changes, swap changes or cache
drops. Faults halt new requests. Do not run other model workloads on these GPUs
alongside LTX. Qwen artifacts and its unresolved USB archive remain protected;
that storage work is not a prerequisite for the next LTX measurement.

Disk policy: continuous video saving is not required. Keep a small set of
canonical reference tensors, selected lossless review samples and at most three
recent campaign preview clips. After exact verification, delete superseded
campaign footage/tensor archives as needed while retaining compact metadata,
hashes, comparisons and deletion receipts. Preserve unresolved failure evidence
and active reference tensors until comparisons finish. Prune only explicitly
identified LTX outputs; model weights and unrelated experiment artifacts are
outside this permission. Deletion never substitutes lower-quality stored
samples for the full-precision verification step.

For each bounded experiment, record hypothesis, exact code/config diff,
identity, command, timing definition, prompt/seed set, output comparisons,
memory/fault observations and a win/loss/inconclusive decision. Work on main;
commit explicit paths and preserve prior receipts. For endurance runs, plan
bounded disk use and retain enough stream state and hashes for replay; durable
recording still needs finite storage and an explicit retention policy.

Work begins with the [30-request stability campaign](data/stability-01-prereg.json)
on the current server, followed by an evidence-backed exact optimization.
Ten prompt/seed fixtures run three times each; the three existing fixtures keep
their original references, while seven new fixtures establish only repeatability
under the current split. Longer soaks wait for unexplained allocation drift to
be resolved. These bounded steps pursue the user's actual under-one-second goal.
