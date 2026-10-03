# One interpreter per stage: design for splitting the LTX pipeline into processes (2026-10-03)

Design only: no runtime code was changed for this note.

## Starting point

[Packet 91b](2026-10-03-packet-91b-results.md) added a second decode worker
(an exact VAE replica on xpu:1, 116/116 clips exact). The stream did not get
faster: mean 1.602 s per clip against 1.663 s for the 90c timers-off control.
Every stage slowed instead:

- **Sampler job:** 2.61 -> 2.96 s.
- **Decode job:** 1.74 -> 2.22 s, by the same amount on xpu:1 and on xpu:3.

The 90c timers showed the sampler cards only 41-45 % busy. The working
hypothesis is therefore that **one Python process issuing work for seven
threads is the bound**: the interpreter lock (GIL), and possibly per-process
driver/runtime locks, rather than the cards. Every proposal below has to
survive a test of that hypothesis first.

Labels used for every number: **[m]** measured (source named), **[p]**
projected, **[?]** unknown.

## 1. The decisive diagnostic (packet 92a, no new process)

We need one live run, on the existing 91b packet shape, that separates "the
process is the bottleneck" from "the cards are the bottleneck". Three
instruments go in one packet. None of them touches a tensor, a stream or the
order of GPU work.

### A. CPU seconds per thread per job (standard library only)

- In `ltx_pipeline._worker_loop`, around `job.fn()`, record
  `time.thread_time()` and `time.perf_counter()` deltas. That gives CPU
  seconds and wall seconds per job, for every encode, sample and decode
  worker.
- Receipts sum CPU seconds over all lane threads per second of stream wall,
  plus the main/prompt thread via the same wrapper around each node's
  `_apply`.
- `thread_time` counts CPU time spent while holding the GIL and also in C code
  that released it. A process whose Python threads together use about one
  core and no more is GIL-saturated. Waiting on the GPU (an event wait or
  synchronize) uses no CPU.

### B. GIL hand-off latency probe

- One daemon thread loops `t0 = perf_counter(); time.sleep(0.0005); lag =
  perf_counter() - t0 - 0.0005` and records a histogram into the sampler
  receipt.
- The lag is the time the thread waits to get the GIL back after its sleep.
  An idle interpreter gives about 0.05-0.1 ms. A contended one gives
  multiples of the 5 ms switch interval.

### C. Switch-interval arms on one server

`sys.setswitchinterval(x)` is set through a small request-level knob node,
the way the decode probe is submitted. It is a pure scheduler knob: it changes
when Python hands the GIL to another thread and nothing else. Arms of 30
prompts each run on one server: default 5 ms, then 1 ms, then 20 ms, then
5 ms again to check for drift.

### Verdict rules

The thresholds below are fixed before the run.

**Confirms "process-bound"** if all three hold in the default arms:

1. Lane threads together use **≥ 0.85 CPU-seconds per wall-second** of stream
   time, and **no thread is ever above 1.0 alone**.
2. The GIL-lag median is **≥ 1 ms**, against **< 0.2 ms** in a warm-up window
   with no prompts.
3. The sampler job or decode job median moves by **≥ 8 %** between the 1 ms
   and 20 ms arms.

Card contention predicts no change from rule 3. Only a shared interpreter
reacts to the switch interval.

**Refutes it** if lane CPU is **≤ 0.6 CPU-s/s**, the lag median is under
0.3 ms, and the switch-interval arms agree within 3 %. In that case the
slowdown is card- or driver-side, and a process split would not help.

**In between:** a split can still remove per-process driver locks, which none
of these instruments can see. Go to 92b, the smallest real split. It is the
end-to-end test either way.

### Why not "run one stage alone with the others idle"

That arm changes the pipeline's shape: fills, queueing and memory state all
differ. A shift could then come from the shape, not the interpreter. The
switch-interval arms keep the shape identical.

## 2. Target architecture

| Process | Cards | Owns | Threads |
| --- | --- | --- | --- |
| **Front end** (the sealed ComfyUI server) | xpu:0, xpu:1 | HTTP and queue, graphs, all gate nodes, oracle capture, the two-clip sampler (packet 94 keeps it here), run-behind ordering, receipts | prompt thread + 2 sampler workers |
| **Encode worker** | xpu:2, xpu:3 | text-encoder shard and its graph capture | 1 issue thread |
| **Decode worker** | xpu:3 (optionally a second one on xpu:1) | video + audio VAE, eager decode, MP4 preview writer | 1 issue thread + writer |

Optional later step, packet 95: **one sampler process per card**. Process A
owns blocks 0-22 on xpu:0 and process B owns blocks 23-47 on xpu:1. The
activations already cross cards through pinned host memory (`staged_move`),
so that buffer becomes shared memory between A and B. Each process then has
one interpreter and one card, and two clips stay in flight as a two-stage
pipeline.

### What crosses each boundary

All of it travels as raw tensor bytes plus a header
`{clip_index, tag, name, dtype, shape, sha256}`:

- **Front end -> encode worker:** `(clip_index, prompt_text, tag=sha256(text))`.
- **Encode worker -> front end:** the conditioning structure (lists, dicts and
  tensors, the same structure `cond_fingerprint` walks), flattened to a
  manifest of tensors plus JSON-able metadata, and rebuilt on receipt.
  - [?] It is not yet checked that the conditioning holds nothing but
    tensors, numbers and strings. Any other object (a hook, a callable) is a
    blocker to be found in 93's first offline test.
- **Front end -> decode worker:** `video_latent['samples']` and
  `audio_latent['samples']`, plus `clip_index`, `save_prefix` and the two
  sha256s that sentry 3 already computes. About 150 KB per clip [m: shapes
  from the probe fixtures].
- **Decode worker -> front end:** images (25x256x256x3 fp32, about 19.7 MB),
  waveform (about 0.4 MB), sample rate, and the decode split timings.
- **Seeds and noise** never cross while the sampler stays in the front end.
  In packet 95 the initial noise is generated in one place, as today
  (serialised), and sent as bytes.

### Transport

Use one `multiprocessing` `Connection` (a socketpair) per worker, with framed
messages: `send_bytes(header)` then `send_bytes(raw)`.

- At about one clip per second, 20 MB per message is a few milliseconds of
  copying.
- A pipe dies with its process, so EOF is the worker-death signal, and there
  are no files to clean up after a crash.
- `/dev/shm` files with a manifest are only worth it in packet 95, where the
  per-step activation handoff must be zero-copy.

### Byte integrity across the boundary

The sender computes the sha256. The receiver recomputes it from the received
bytes before building the tensor (`torch.frombuffer(...).view(dtype).reshape(shape).clone()`).
A mismatch raises.

- The existing sentries keep their meaning: sentry 3 (decode submit) still
  runs in the front end on the tensor before it is sent.
- A new **sentry 3b** checks that the worker received the same bytes.
- On the way back, the worker's output sha256 must match what the front end
  received.

### Ordering, latch, markers, oracle

- **Ordered emission is unchanged.** `ltx_pipeline.run_behind` stays in the
  front end. The job function a front-end thread runs becomes "send clip *i*
  to the worker, block on its reply for clip *i*". The worker handles
  requests in arrival order. `collect(index)` still releases strictly by
  index, the mechanism that kept 116/116 exact in 91b.
- **Fail-closed latch.** A worker exception comes back as an error reply. The
  job fails, `collect` raises, and the node latches as today. A dead worker
  (EOF or timeout) is the same failure. Workers never restart themselves.
- **Done markers.** The worker writes `pipeline-done-<stage>-<index>.json`
  after its GPU work finishes and before replying. The front end also
  records reply arrival. The quiescence stop requires both, plus an idle
  confirmation from each worker over its pipe.
- **Exactness oracle is untouched.** The decode node returns the received
  tensors into the graph, so node 414 captures the same four tensors and
  `compare-clip.py` compares them against the references.

## 3. What has to change in the sealed machinery

Recommendation: **one front end plus worker processes that import only torch,
the lane modules and the ComfyUI model code they need.**

- `comfy.sd` and `comfy.ldm.lightricks.vae` for decode.
- `comfy.sd` and the text-encoder modules for encode.
- No HTTP server, no executor and no node registry in the workers.

Why not three ComfyUI instances on three ports:

- The sealed launcher takes exclusive locks on all four GPUs
  (`/tmp/b70-gpu{0..3}.lock`, `/run/lock/muse-glimmer-gpu-exclusive.lock`).
- It requires `fuser` to show the render devices unowned.
- It binds port 8188.

A second launcher would fail all three checks. Loosening them for three
servers means three fault watchers, three identities and cross-server prompt
choreography. That is more surface for no extra separation.

### Changes, smallest first

**Launcher (`serve-encoder.py`):**

- No new lock and no change to the preflight. It runs the four-card preflight
  exactly as now.
- After that, and before `runpy` hands control to ComfyUI, it spawns the
  workers with `multiprocessing.get_context('spawn')`. The worker entry point
  is a packet file whose sha256 is in the manifest.
- Workers inherit no locks. The launcher keeps the flock for the life of the
  supervision. A worker exits when its pipe reaches EOF, so it cannot outlive
  the launcher.
- The "Expected four XPU devices" check stays in the front end only.

**Fault gate:** stays in the launcher. On FAULT it writes `FAULT.json`
(workers check it before each job, as the client does) and sends a "halt"
message to each worker. It never kills them.

**Server identity:** `server-identity.json` gains a `workers` list with name,
pid, `proc_start_ticks`, device set, module sha256s and the worker's own
`identity_sha256`. Each worker writes `worker-identity-<name>.json`, and nodes
verify it before using that worker.

**Graph gates:**

- The VAE gate stays in the front end in `original` mode, as in every arm
  since 74.
- The text-encoder graph gate (graph-shard capture on xpu:2/xpu:3) moves into
  the encode worker. The front-end gate node becomes a pass-through that
  forwards the mode and records the worker's capture report.

**Capture exclusivity across processes (new):**

- `CAPTURE_LOCK` is per process, so it cannot cover two processes on the same
  card.
- In 93, xpu:3 carries the encode worker's graph captures and the decode
  worker's eager work. That needs a cross-process reader/writer lock per
  card: `fcntl.flock(LOCK_SH / LOCK_EX)` on `/dev/shm/ltx-capture-xpu3.lock`.
  Captures take it exclusive and replays and eager stage work take it shared.
  This is the same contract as 91b's lock, extended across processes.
- Lock order: the in-process `CAPTURE_LOCK`, then the cross-process card
  lock. Never the reverse.

**ComfyUI itself:** unchanged. The decode and encode nodes become proxies
that talk to the workers.

## 4. Device visibility

Recommendation: **the front end keeps all four cards and today's literals.
Each worker is restricted to its own cards with `ZE_AFFINITY_MASK`, set in
the child's environment only.**

- The launcher refuses that variable in its own environment (line 126), and
  that check stays.
- A worker that sees only xpu:3 calls it `xpu:0`. Worker code is new, so it
  takes its device indices from a config map (`{'decode': 'xpu:3' -> local
  0}`), never from a literal.
- Restriction keeps each worker from creating a Level Zero context, and the
  VRAM that context costs, on cards it does not use [?: per-context VRAM cost
  on this driver is unmeasured; 92b's receipts should record it]. It also
  makes "one process initialising a card at a time" enforceable.

Hardcoded device literals and pins: these would be wrong if imported inside a
restricted worker, but stay correct in the front end.

| Location | Literal(s) | Notes |
| --- | --- | --- |
| `ltx_layer_shard.py:218` | `"xpu:0"`, `"xpu:1"` | Shard routing. Sampler stays in the front end until 95, which needs per-card rework. |
| `resident_node.py:79/98/104` | `xpu:2` (CLIP), `xpu:3` (VAEs), `xpu:1` (shard) | |
| `host_embedding_resident_node.py:157/170/178` | `xpu:2`, `xpu:3`, `xpu:1` | The active loader: CLIP load device, VAE device, shard secondary. |
| `host_embedding_clip_threadsafe.py:285` | `xpu:2` | |
| `graph_text_encoder_node.py:26` | `xpu:2`, `xpu:3` | Text shard placement. Moves into the encode worker in 93 and must take the map. |
| `ltx_decode_replica.py:57-58` | `NATIVE_DEVICE='xpu:3'`, `REPLICA_DEVICE='xpu:1'` | |
| `pipeline_decode_node.py` | `xpu:1` memory reads in the probe (`_xpu_memory(1)`) | |
| `pipeline_sampler_node.py:180` | `torch.device('xpu', i) for i in range(2)` | |
| Memory loops over `device_count()` | — | Sampler, graph, VAE, fusion, text and pipeline nodes, `ltx_graph_capture.py:879`, `concurrent_cfg_node.py`. They report fewer cards under restriction; harmless, but the receipts change shape. |
| `serve-encoder.py` | `device_count() == 4` and the `xpu:{i}` preflight loop | Front end only. |
| Embedded checker (`prepare-graph-capture-runtime.py` NEW_VERIFY) | `decode_placement` `native_device == 'xpu:3'`, `replica_device == 'xpu:1'`, `split_index`, the shard arms | |

None of the model or identity sha256 pins depend on device numbering.

## 5. Memory

### Host RAM

Measured in 91b's server [m, `encoder-server-decode-91b/host-components-01-control-*-memory.json`]:

| Field | Before CLIP construction | After construction |
| --- | --- | --- |
| MemTotal | 115 GiB | 115 GiB |
| MemAvailable | 70 GiB | 53 GiB |
| AnonPages | 41 GiB | 58 GiB |
| Cached | 43 GiB | 53 GiB |
| Mapped | 0 | 25 GiB (mmapped safetensors) |
| Committed_AS | 46 GiB | 95 GiB |
| Swap | 7 GiB free | full |

- The admission gate budgeted 52.5 GB of tracked host allocation for CLIP
  construction. The CLIP is built on CPU, `offload_device=cpu`, then loaded
  to xpu:2, with the embedding table host-resident by design.
- During the 90c run MemAvailable was about 17 GiB [m, 90c results note].
- [?] I could not attribute the 41 GiB of anonymous memory present before
  construction. It is likely the transformer and VAE loads staged through
  host memory, plus torch and inductor state, and possibly other processes.
  Before planning further, 92a's receipts should add the server's own
  VmRSS/RssAnon (`/proc/self/status`) per stage.

Projection for the split [p]:

- Moving a stage moves its host footprint; it is not duplicated, provided the
  front end no longer loads that component.
- Each new interpreter adds its own torch/oneAPI runtime and imports:
  [p] roughly 2-4 GiB RSS each [?: measure it in 92b].
- Construction transients (CLIP on CPU, about 15 GB) must stay serial.
- Total: today's footprint plus about 4-8 GiB for two workers. Against
  17 GiB available in 90c, that leaves about 9-13 GiB.
- **Fits, with a thin margin.** It does not fit if a worker re-reads a model
  through anonymous memory while the front end still holds its copy. Each
  packet's admission gate must check `MemAvailable` before every worker
  construction, as `host_embedding_transition_memory` already does.
- Swap is already full at construction, which is a pre-existing risk.

### VRAM per card

Today's single process [m, f90c receipts; total 31.89 GiB per card]:

| Card | Today (one process) | After the split [p] |
| --- | --- | --- |
| xpu:0 | 28.5 GiB reserved | Unchanged until 95. |
| xpu:1 | 24.24 GiB reserved (shard 19.33 GB) | Unchanged. The optional decode replica in its own process needs 1.71 GiB of weights, a working set of up to 4.8 GiB [m, xpu:3 bound] and its own context [?]. 91b measured 3.41 GiB free with the replica inside the front end [m]. In a separate process the decode cache cannot reuse the sampler's freed blocks, so expect about 2-3 GiB free. **Tight: keep the xpu:1 replica out of 92/93 and decide in 92b from measured context cost.** |
| xpu:2 | up to 21.61 GiB reserved | Encode worker; unchanged plus a context. |
| xpu:3 | up to 16.64 GiB reserved (text shard 10.9 GB + VAEs 1.84 GB, one allocator) | Split across two processes: about 13-14 GiB (encode) + about 2-6.6 GiB (decode) + two contexts. **Fits** with about 10 GiB spare. |

## 6. Startup and teardown

The rule: **one card-initialising transition at a time, each confirmed before
the next starts. Never start a worker while another process is loading or
capturing.**

### Startup

1. The launcher preflights all four cards (as today). The front end imports
   ComfyUI and starts the HTTP server without loading models.
2. Spawn the **decode worker**. It loads the VAEs on xpu:3, decodes one fixed
   probe latent and compares it to the reference sha256, writes its identity
   receipt, then sends `ready`.
3. Spawn the **encode worker**. It constructs the CLIP on CPU (memory
   admission first), loads the shard onto xpu:2/xpu:3, captures its graphs
   under the cross-process card locks, writes its receipt, then sends
   `ready`.
4. Only then does the runner's health wait succeed: the `/queue` answer is
   gated on workers being ready. Then the 60 s rest and the warm arm, whose
   first prompt loads the transformer and captures the sampler graphs in the
   front end, as today.

Doing the workers first means no worker initialises a card while the front
end captures sampler graphs on xpu:0/xpu:1.

### Supervised stop

Same proven-quiescence rule as 90c/91b, plus worker idle confirmation:

- The queue is empty.
- Every done marker exists.
- Each worker answers `idle` with nothing in flight.

Then, in reverse order of start:

1. `stop` to the encode worker: it finishes nothing new, frees, exits 0.
   Join it with a timeout.
2. `stop` to the decode worker; join it the same way.
3. Exactly one SIGINT to the launcher, which exits the front end.

A worker that does not exit inside its timeout is reported and left alone.
There is never a kill escalation, because bare kills have faulted the GPU on
this host. If one worker dies, that is a latch: the others are left up, and
the runner exits non-zero for review.

## 7. Expected speed

| Quantity | Value | Source |
| --- | --- | --- |
| Budget for 24 fps | 1.042 s/clip | 25 frames / 24 |
| Sampler, one clip, serial, nothing else running | 1.98 s | [m] three-stage-pipeline-01, encode-ahead-01 (pre-graph-capture era; not re-measured on 90c code) |
| Sampler card time per clip | xpu:0 0.76 s, xpu:1 0.84 s | [m] 90c busy windows (timers on) |
| Sampler weight-read floor | 0.74 s/clip | [m] encode-ahead-01 |
| Two-clip sampler, pipelined today | 2.61-2.96 s per job = 1.31-1.48 s/clip | [m] 91b control / replica |
| Decode, alone | 0.71 s (video + audio) | [m] f84 receipt, via the timing-evaluation note |
| Decode, pipelined today | 1.74 s (1 worker), 2.22 s (2 workers) | [m] 91b |
| Encode, one card, alone | 1.59 s | [m] encode-ahead-01 |
| Encode, sharded on xpu:2/3, isolated | about 0.85 s/clip | [p] shard design estimate, capacity-budget note |
| Encode, pipelined today | 3.1-3.2 s per job, two in flight = 1.57 s/clip | [m] 91b |

If every stage ran at its stand-alone time [p]:

- The interval is set by the slowest stage.
- Encode (sharded) about 0.85 and decode 0.71 are both under the budget.
- The two-clip sampler in its own interpreter is the open number.
  - At best, two clips overlap perfectly on two cards: about 1.98/2 =
    0.99 s, and no lower than card time (0.84 s).
  - But that process still has **two threads sharing one GIL**. If the
    host-side issue between replays is about 1.1 s per clip (1.98 serial
    minus about 0.84 card) and holds the GIL, two threads need about 2.2 s
    of GIL per pair, which is **about 1.1 s/clip**.
- So the front-end-sampler architecture (92-94) projects to **about
  1.1-1.4 s/clip**, against 1.60 today.
- The remaining gap to 1.042 closes only if the sampler's issue path stops
  sharing an interpreter (95: per-card processes, about 0.85-1.0 s/clip [p])
  or if issue time per replay drops (fewer, larger graphs: the c48 chain
  arms).

## 8. Staged build plan

Each packet answers one question. Each must keep **100 % exactness on the
ten-fixture harness** (oracle on every emitted clip). Each is selected per
request or per launch, so dropping it leaves the previous packet's arms
runnable unchanged.

| Packet | Question | Change | Gate to continue |
| --- | --- | --- | --- |
| **92a** | Is the slowdown the shared process? | The §1 instruments plus the switch-interval knob, on 91b's code. No new process. | The verdict rules in §1. If refuted, stop the split and look at the driver and cards. |
| **92b** | Does the smallest split speed things up, and does it stay exact? | Decode in a child process on xpu:3 (pipe transport, sha256 at both ends, sentry 3b), selected by a new arm next to the in-process decode. The 92a instruments stay on. | 117/117 exact. Decode job median ≤ 1.0 s **and** sampler job median down ≥ 8 % against the in-process arm on the same server. Measured per-process host RSS and per-context VRAM. |
| **93** | Does encode out of the interpreter remove the encode cap? | Encode worker on xpu:2/xpu:3 with the text graph capture, cross-process card locks on xpu:3, conditioning manifest transport. | Exact. Encode ≤ 1.0 s/clip. Stream mean below 92b's. Conditioning byte-equality test offline before any launch. |
| **94** | Where does the two-clip sampler land alone in the front end? | No new mechanism. The front end runs only the sampler, plus thin proxies and the oracle. Measure with the 92a instruments. | A number: sampler s/clip and its GIL share. If at or under about 1.1, stop here. |
| **95** | Do per-card sampler processes reach the budget? | Blocks 0-22 and 23-47 in two processes, activations through pinned shared host buffers, two-stage clip pipeline. Largest change; designed only if 94 shows the sampler's own GIL as the bound. | Exact. Interval ≤ 1.05 s. |

## 9. Risks and open questions

1. **Cross-process capture exclusivity on shared cards (xpu:3 in 93).** The
   in-process lock does not reach another process. The `flock` design is
   simple, but graph capture empties the device cache, and whether the
   capture tolerates another process's allocations at all on this driver is
   [?].
2. **Per-process Level Zero contexts.** VRAM cost [?]. Whether two contexts
   submitting to one single-CCS card interleave as well as two threads in
   one context do [?]. It may be worse: separate contexts time-slice where
   one context could share queues.
3. **Host RAM.** About 41 GiB of the baseline is unattributed and swap is
   already full. A new interpreter's runtime and inductor footprint is [?].
   This could make the split not fit without first reducing the front end's
   host copies.
4. **Conditioning serialisability [?].** If the conditioning holds a non-tensor
   object (a hook or patcher reference), the encode boundary needs a
   reconstruction step that is itself an exactness risk.
5. **Two sampler threads still share one GIL in the front end.** The split
   may stop at about 1.1-1.4 s/clip (§7) until 95, and 95 is a large
   change: pipeline-parallel processes with shared pinned buffers.
6. **More transitions per launch.** Three processes initialise and tear
   down. This host's faults cluster on transitions. Mitigation: strictly
   serial readiness (§6) and no kill escalation. The risk itself is
   unchanged in kind and higher in count.
7. **Unanswered by the code:**
   - Whether torch's XPU calls release the GIL during kernel submission. If
     they hold it, the GIL share is larger than the CPU-time estimate.
   - How much SYCL runtime locking exists per process.
   - Whether `time.thread_time` on this kernel counts time spent in driver
     ioctls as expected.

   92a's instruments measure the first and third. The second shows up only as
   a residual in 92b.
