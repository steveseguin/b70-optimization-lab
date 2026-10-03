# Packet 92b: decode in its own process (build, 2026-10-03)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

## The question

[92a](2026-10-03-packet-92a-results-and-freeze.md) ruled out the interpreter
lock:

- The lock-wait median under load was 0.064 ms, the same as idle.
- The 1 ms and 5 ms switch-interval arms agreed within 0.5 %.

It also showed that the lane threads are close to CPU-bound in native code:
3.8-3.9 CPU-s per wall-s, with the busiest thread at 0.83-0.89. Whatever the
threads share is below Python. One candidate is per-process GPU runtime state
(a SYCL or Level Zero lock, scheduler or context).

A decode child process gets its own interpreter, its own SYCL runtime and its
own Level Zero context. 92b is therefore a direct test of that candidate.

**The rule, fixed before the run.** Both arms must be all-exact. If the child
arm's sampler **and** encode job medians are each at least **8 % lower** than
the control arm's, the process split continues. If neither improves by 8 %,
it stops. Anything else is MIXED.

## Design as built

**Arms.** The arm is selected per request, as in 91b:

- `pipe-samp2-tsh` (mode `pipeline-save`): the control. Decode runs in-process
  on xpu:3, exactly as in 90c and 92a.
- `pipe-samp2-tsh-child` (mode `pipeline-child`): every clip is decoded by the
  child, also on xpu:3. The first split stays on the card that already hosts
  decode.

**Spawning** (`ltx_decode_child.py`):

- When `LTX_DECODE_CHILD=1`, the decode node module spawns the child once per
  server, at custom-node import time. That is after the launcher's four-card
  preflight and before ComfyUI starts serving. Nothing else is initialising a
  card at that point, because model loading happens at the first prompt.
- The spawn uses `subprocess` with a socketpair `Connection`, not
  `multiprocessing` spawn. `multiprocessing` spawn would re-import ComfyUI's
  `main.py` in the child.
- The launcher is unchanged.
- `decode-child-startup.json` records the configuration, the child's pid and
  its ready report.

**The child process:**

- It sees only xpu:3 (`ZE_AFFINITY_MASK=3`, set only in the child's
  environment).
- The uuid of its single device must equal the front end's
  `torch.xpu.get_device_properties(3).uuid`, otherwise it refuses to start.
- It sets the server's own argv and parses it before importing
  `comfy.model_management`, so the `--bf16-vae`, deterministic and attention
  flags match.
- It applies strict determinism, as the launcher does.
- It imports only `comfy.sd`, `comfy.utils` and their dependencies: no custom
  nodes, no HTTP server, no executor.
- It loads its own copy of both VAEs exactly as the resident loader does
  (`comfy.sd.VAE(sd=..., device=xpu)`), reports `ready`, then decodes
  requests one at a time.
- Its decode mirrors the node's native path: `vae.decode`, the VAEDecode
  reshape, then `audio_vae.decode(...).movedim(-1, 1)`. The front end moves
  the waveform to the audio latent's device and the images to the VAE's
  output device, as the native nodes do.

**Transport.**

- One JSON header, then one raw-bytes message per tensor.
- Each tensor entry carries dtype, shape, nbytes and the sha256 of its bytes,
  using the oracle capture's convention.
- The receiver checks the length and the sha256 before building the tensor,
  in both directions. The child echoes the hashes it received, and the front
  end requires them to equal what it sent.
- A hash mismatch, a short payload, EOF (child death) or a 180 s reply
  timeout raises. The decode job fails, `collect` raises, and the node latches
  fail-closed, as in every packet.

**What stays in the front end.** `run_behind` ordering, the three sentries
(sentry 3 hashes the exact latent bytes that are sent), done markers, the
preview writer and the oracle capture.

**Capture exclusivity across processes.** Each child round trip holds the
front end's `CAPTURE_LOCK` in shared mode, which is the 91b discipline
extended across processes. No front-end graph capture can start while the
child is decoding, including the text shard's captures on xpu:3. The child is
only ever sent work by a thread holding that lock.

- Lock order: `_CHILD_LOCK` -> `CAPTURE_LOCK` (shared).
- This needed no new mechanism. The obstacle the design note feared (an
  in-process lock cannot reach another process) is avoided because all the
  child's GPU work is requested, synchronously, from inside the front end.

**Probe** (`LTXDecodeChildProbe`, graph `graphs/decode-child-probe.json`).
The child decodes the ten fixtures' certified latents, the same pinned
`probe/decode-replica-fixtures.json` as 91b. The probe requires:

- every image and waveform to equal the stored references byte for byte;
- device-wide free memory on xpu:3 of at least **5 GiB after the child
  loads** and at least **1 GiB after the decodes** (`mem_get_info`, same
  thresholds as 91b).

Any other verdict stops the child cooperatively and refuses the child arm
with a recorded outcome: `child-not-exact`, `insufficient-memory`,
`child-unavailable` or `error`. The child's memory goes with its process; the
receipt records xpu:3 free memory before and after the stop.

**Stop** (`LTXDecodeChildStop`, graph `graphs/decode-child-stop.json`).

- It waits up to 60 s for the pipeline to go idle, then sends `stop` and waits
  up to 120 s for the process to exit. It never kills.
- The runner's proven-quiescence stop runs this after the queue and the done
  markers check out. It then confirms the child pid is gone, and only then
  sends one SIGINT to the launcher.
- If the child does not exit, the server is left up and the runner exits 7.
- An `atexit` hook in the server also asks a still-running child to stop.
- A child whose parent disappears sees EOF and exits.

**Instruments.** The 92a per-thread CPU snapshots and the lock-wait probe stay
in the front end; together they cost about 1.5 % of a core. Every child reply
carries the child's per-job `thread_time` and its own `/proc` CPU snapshot. The
analyzer reports CPU-s per wall-s separately for the front-end lane threads
and for the child process.

**92a review fixes.**

- The `thread_time` calls next to `job.done.set()` are wrapped, so a clock
  error cannot strand a job.
- `analyze-gil-92a.py` tolerates missing arms instead of dividing None.

## VRAM on xpu:3

| Item | Value | Source |
| --- | --- | --- |
| Peak today, one process | 13.98 GiB allocated, 16.64 GiB reserved | measured: 92a and 91b sampler receipts |
| Resident weights | text shard 10.9 GB + video VAE 1.47 GB + audio VAE 0.36 GB | |
| Driver overhead beyond torch's reserve | about 0.5 GiB | measured on xpu:1 in 91b: 24.2 GiB reserved, 7.15 GiB free of 31.89 |
| VAE copy in the child | 1.71 GiB | |
| Decode working set | about 2.0 GiB | measured: the 91b probe's xpu:1 free fell 5.41 -> 3.41 GiB after ten decodes |
| Child context | unknown | |

During the child arm the server keeps its own VAEs and its cached decode
blocks, but they stay idle.

Projected free memory on xpu:3:

- about 14.8 GiB with the child absent;
- **about 10-11 GiB** with the child loaded and decoding.

That is well above both probe thresholds. If the child's context costs far
more than expected, the probe refuses instead of letting the card page.

## Packet and gate

- **Packet:** `R/prepared-encoder-decodeproc-92b`, **manifest sha256
  `988884d33df4bf9c35cfadb0edd331377940ec2d3bcf3e0c720183cac54e051f`**.
- **Compared with 92a:**
  - Added: `ltx_decode_child.py`, the child arm graph, and the child
    probe/stop graphs.
  - Changed: `ltx_pipeline.py`, `pipeline_decode_node.py` and its node copy,
    `ltx_decode_replica.py` (one placement entry), and the checker.
- No stale pins, and custom-node imports resolve. The generator ran after the
  92p profiling server had exited.

`--check-only` output, server_args elided:

```
gate rc=0
{
  "status": "inactive-startup-check-passed",
  "run_dir": ".../encoder-server-decodeproc-92b",
  "packet_manifest_sha256": "988884d33df4bf9c35cfadb0edd331377940ec2d3bcf3e0c720183cac54e051f",
  "limits": "No device discovery, locks, process changes or GPU work; exclusive preflight occurs only at launch"
}
```

## Launch

The server is launched with timers off (speed comparison) and the child
enabled. The runner refuses otherwise.

```
P=/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-decodeproc-92b
nohup env LTX_BUSY_WINDOWS=0 LTX_DECODE_CHILD=1 /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 988884d33df4bf9c35cfadb0edd331377940ec2d3bcf3e0c720183cac54e051f --run-name encoder-server-decodeproc-92b > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-decodeproc-92b.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-92b.sh > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/campaign-92b.log 2>&1 &
```

`run-campaign-92b.sh` runs at the default switch interval only; there is no
knob and never 20 ms.

| Step | Prompts | Index base | Client bound | Clips verified |
| --- | --- | --- | --- | --- |
| warm (`pipe-samp2-tsh`) | 3 | 210089 | 900 s | 0 (fills) |
| child probe | - | - | 1500 s | 10 fixtures vs references |
| control (`pipe-samp2-tsh`) | 40 | 210189 | 2400 s | 37 |
| child (`pipe-samp2-tsh-child`), only if the probe passed | 120 | 210289 | 3600 s | 117 |

- Exactness is checked per arm.
- Sync runs after every arm and every 10 completed child-arm prompts.
- The stop order is: queue empty and every done marker present, then the
  child stopped and confirmed gone, then the server stopped.

## Reading the result

```
/home/steve/.venvs/ltx25-baseline/bin/python -B /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/analyze-decodeproc-92b.py \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-decodeproc-92b \
  /home/steve/llm-optimizations/experiments/ltx25-b70/data/decodeproc-92b
```

For each arm it prints:

- exactness and the stream interval median/mean;
- sampler, encode and decode job medians;
- front-end lane CPU-s per wall-s and the busiest thread;
- the child's CPU-s per wall-s;
- the lock-wait median;
- the 8 % verdict.

## Tests (CPU only, lane venv, no XPU initialised)

| Test | Result |
| --- | --- |
| `test-packet92b-decode-child-cpu.py` | 6/6, using a fake child that speaks the real protocol |
| `test-packet92a-gil-probe-cpu.py` | 8/8 |
| `test-packet91-decode-placement-cpu.py` | 11/11 |
| `test-packet90c-instrumentation-stdlib.py` | 6/6 |
| `test-ltx-graph-capture-stdlib.py` | pass |
| `test-ltx-pipeline-lookahead.py` | 7/7 |
| `test-packet-custom-node-imports-cpu.py` | pass |

The 92b tests cover:

- framing: round trip, sha256 mismatch, short payload, EOF mid-message;
- lifecycle: ready, request, child death mid-job latches, a corrupt reply is
  refused, cooperative stop exits 0;
- ordered emission through the decode node with a slow child;
- the fail-closed probe: mismatch, low memory at load and after the probe,
  and an unavailable child all stop the child and keep the arm refused, while
  an exact probe admits it;
- the stop node: refuses while busy, and the child exits 0 when idle;
- both 92a review fixes.

## Unverified offline

- **The real child is not exercised offline.** That covers its startup
  (argv parsing, model-management import side effects, `ZE_AFFINITY_MASK`
  numbering, the uuid check) and whether its VAE construction yields
  byte-identical decodes. The probe decides the last point.
- **Whether a second Level Zero context on xpu:3 coexists safely with the
  server's** (text-shard graph replays, VAEs) on this driver. Capture overlap
  is excluded by the lock; plain co-residency of two contexts on one card is
  new for this lane. The host's record of freezes at transitions applies:
  the child is one more process start and stop.
- **The child context's VRAM cost.** The probe measures it, device-wide.
- **Whether the child's own runtime instance actually removes the shared
  native-code bottleneck.** That is the question this run answers.
