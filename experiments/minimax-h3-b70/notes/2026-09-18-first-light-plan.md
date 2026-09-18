# MiniMax-H3 first light, attempt 3: the exact session sequence

Date: 2026-09-18. Supersedes the sequence armed as `h3-session5-20260918` (which died with the
host, see [the stand-up note](2026-09-18-standup-prep.md) and
[the host OOM incident](../../qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md)).

The difference from attempt 2 is not the pipeline. The pipeline was never shown to be wrong -- it
never got past `encode.load`. The difference is that **the host-RAM question is now answered before
the GPU is touched, and every step has something that kills our job instead of the user's session.**

**STATUS 2026-09-18 15:06 UTC: this plan is HALTED at step 4 by a GPU fault.** Session 10 ran
steps 1-4 and the run died three seconds into sampling with a copy-engine fault on `0000:03:00.0`
(xpu:0); the host, the loader and the two-card load all behaved. The full write-up is
[the fault note](2026-09-18-gpu-fault-first-light.md). No GPU work happens on this host until the
user chooses between a health probe and a reboot; the FP8 service is down until then. What
follows is updated with what sessions 9 and 10 established, so the next session can resume from
step 4 rather than re-derive it.

---

## Step 0 -- preconditions, all of them, in order

| # | Precondition | How it is checked |
| --- | --- | --- |
| 1 | The host-RAM need of `encode.load` is **measured**, not argued | step 2 below |
| 2 | That measured peak sits well under free host RAM | the go/no-go rule below |
| 3 | No cgroup `MemoryMax` below the measured peak | `smoke_h3.sh` sets `MemorySwapMax=0` and **no** memory ceiling; do not add one |
| 4 | Nothing else running: no build container, no other lane, service down | `smoke_h3.sh preflight` refuses: MemAvailable < 11 GiB, port 18124 listening, or any running container |
| 5 | The service restore waits for the port | step 7 below |
| 6 | Queued behind the FP8 work, not beside it | the session script's `until ! systemctl --user is-active ...` waits |
| 7 | `PYTORCH_ALLOC_CONF=expandable_segments:True` in the run's environment (**new, session 10**) | `smoke_h3.sh` exports it for every GPU run and prints it in preflight |
| 8 | No card carries an uncleared device coredump (**new, session 10**) | `smoke_h3.sh preflight` refuses and names the card |
| 9 | The step count is not a guess (**new, session 11**) | settled: `--steps` = NFE + 1; 51 base, 9 with the turbo LoRA, which is on disk and applied by default. [notes/2026-09-18-steps-and-lora.md](2026-09-18-steps-and-lora.md) |

Preconditions 7 and 8 are not style. Without 7, every GiB placed on a card costs a GiB of host RAM
with both cards visible, which is what killed session 9; without 8, a run starts on a card whose
last fault has never been cleared, which is exactly the state this host is in now.

## Step 1 -- regenerate the rotation, and re-run the CPU gates (seconds, safe now)

`./scripts/smoke_h3.sh dry` now runs five gates, not three: the two `--dry-run --verify-remap`
passes (which also report the LoRA mapping, 208/208 pairs matched), `test_convrot_linear.py` and
`test_lora.py`. All pass as of 2026-09-18.


```bash
cd /home/steve/b70-optimization-lab/experiments/minimax-h3-b70/scripts
/mnt/fast-ai/venvs/minimax-h3-cpu/bin/python recover-convrot-rotation.py \
    --out ../data/convrot-hadamard-256.safetensors
./smoke_h3.sh dry          # 14/14 remaps exact, 634 params from 532 tensors, 0 left over
```

`data/convrot-hadamard-256.safetensors` is not in Git (`*.safetensors` is ignored); the regenerated
file must have sha256 `ebb89aa1651e681f49461fe539bf2eb6fba0143c2733e5ad9cef438d48fb28d2`.

## Step 2 -- the CPU host-memory profile, under the watchdog (safe now, service up)

**Done, and it is a GO -- but only after the loader was replaced.** The history is below; the
commands as they stand now are:

```bash
/mnt/fast-ai/venvs/minimax-h3-cpu/bin/python profile-encoder-load.py \
    --json /mnt/fast-ai/bench-results/minimax-h3/host-mem/encoder.json
/mnt/fast-ai/venvs/minimax-h3-cpu/bin/python profile-encoder-load.py --denoiser \
    --json /mnt/fast-ai/bench-results/minimax-h3/host-mem/denoiser.json
```

Both arm `mem-watchdog.sh` on their own pid at a 2048 MiB floor, in their own process group. Both
default to the `pread` loader (`--loader mmap` re-runs the old path for the A/B) and stop at 6 GiB
of tensor bytes -- enough to see the curve, nowhere near the host limit.

### Sessions 6 and 7: NO-GO on the mmap loader

`/mnt/fast-ai/bench-results/minimax-h3-s6-20260918/` (plain) and `-s7-` (`--drop-pagecache`), both
at the 6 GiB budget, `safetensors.safe_open`:

| Run | RssAnon | RssFile | GO/NO-GO (`max(anon+file, VmHWM)`) | Verdict |
| --- | --- | --- | --- | --- |
| s6 encoder | 1.661 GiB | 6.291 GiB | **6.634 GiB** | NO-GO |
| s7 encoder, `--drop-pagecache` | 1.661 GiB | 6.352 GiB | **6.695 GiB** | NO-GO |
| s6 denoiser | 0.499 GiB | 3.906 GiB | 4.192 GiB | under, but on the same curve |
| s7 denoiser, `--drop-pagecache` | 0.499 GiB | 3.977 GiB | 4.260 GiB | under, but on the same curve |

RssAnon was never the problem: it peaked at one tensor's worth (the encoder's largest tensor is
`model.embed_tokens.weight`, 1.556 GB) and came straight back down, which is what a streaming
loader should do. **RssFile was the problem, and it grew with every byte touched** -- 6.29 GiB at a
6 GiB budget, i.e. on the full files it would reach 27 GB for the encoder and 40 GB for the
denoiser. `--drop-pagecache` made it *worse*, not better, and that is the diagnosis: a `safe_open`
handle keeps the whole file mapped for its lifetime, and `posix_fadvise(DONTNEED)` cannot evict a
page that is still mapped. Mapped file pages are reclaimable, so this is not an OOM -- it is worse
for us: the kernel reclaims them through rmap under a streaming read, and sustained reclaim is
exactly the memory PRESSURE `systemd-oomd` kills the user's whole session on
([the incident](../../qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md)).

### The fix: `B70_H3_LOADER=pread` (the default since 2026-09-18)

Both load loops in `run_h3_t2v.py` now go through `open_tensor_reader()`. The `pread` reader parses
the safetensors header once, `os.pread`s each tensor's byte range into a private buffer,
`torch.frombuffer(...).view(dtype).reshape(shape)` re-labels it, the caller copies it to its card,
and `release()` then `posix_fadvise(DONTNEED)`s *that range only* -- which works, because nothing
maps it. Row slices are contiguous byte ranges, so the qkv split now reads a third of `qkv_proj`
three times instead of the whole tensor three times. `B70_H3_LOADER=mmap` restores the old path.
`scripts/test_tensor_reader.py` is the guard that the swap changed only where the bytes live:
`torch.equal`, bitwise, against `safe_open` for every dtype both checkpoints use (BF16/F16/F32/I8/
U8/BOOL/I64), for leading-row slices, and for real safetensors files on disk.

### Session 8: GO

`/mnt/fast-ai/bench-results/minimax-h3-s8-20260918/`, `--max-bytes 2` (the FP8 service was up and
holding ~10 GiB, so the budget was cut to 2 GiB; the curve is flat, so the budget does not change
the peak), same script, same watchdog, both loaders:

| Loop | Loader | RssAnon | RssFile | VmHWM | GO/NO-GO |
| --- | --- | --- | --- | --- | --- |
| encoder | **pread** | 1.593 GiB | **0.070 GiB** | 1.663 GiB | **1.663 GiB -- GO** |
| encoder | mmap | 1.593 GiB | 2.081 GiB | 3.114 GiB | 3.115 GiB |
| denoiser | **pread** | 0.720 GiB | **0.073 GiB** | 0.791 GiB | **0.792 GiB -- GO** |
| denoiser | mmap | 0.432 GiB | 2.053 GiB | 2.483 GiB | 2.485 GiB |

Read it in one line: **on the mmap loader RssFile equals the bytes read (2.05-2.08 GiB of a 2 GiB
budget); on the pread loader it is 0.07 GiB and does not move**, and 0.07 GiB is the interpreter
and torch's own shared objects, not the checkpoint. The peak is now one tensor's worth of anon and
nothing else, so it is bounded by the largest tensor in the file and **not** by the file's size --
the number above is the number for the full 27 GB and 40 GB passes too.

The denoiser's RssAnon goes up (0.432 -> 0.720 GiB) and that is honest: the mmap path could slice
and `torch.cat` straight out of the mapping, while pread holds a real buffer for the source rows
*and* the `cat`/`contiguous` copy at the same time. Paying 0.29 GiB of anon to not pay 2 GiB (and
rising to 40) of mapped page cache is the trade, and the peak is still one tensor's worth.

### The go/no-go rule

> **GO if the encoder profile's peak RSS + RssFile is under 6 GiB, on the `pread` loader.**
> **NO-GO otherwise.**

The script prints exactly that number as `GO/NO-GO NUMBER` (`max(peak anon+file, VmHWM)`; VmHWM
catches any transient a sample missed). 6 GiB is the honest budget: the FP8 service is down for the
run, so the host has roughly 13-14 GiB available, the watchdog floor takes 2 GiB, the XPU runtime
and the rest of the process take a few, and anything under 6 GiB leaves the margin that the
2026-09-17 run did not have. **Status: GO at 1.663 GiB (encoder) and 0.792 GiB (denoiser).**

**On NO-GO the loader changes before the run does.** That is what happened here: sessions 6/7 were
a NO-GO, the loader was replaced, and session 8 re-measured. NO-GO does not mean "try it and
watch".

### Session 9: NO-GO on host memory, with the runner innocent

`/mnt/fast-ai/bench-results/minimax-h3-s9-20260918/`. The first smoke run under the `pread` loader
was killed by `mem-watchdog.sh` at 1.2 GiB MemAvailable during `encode.load` -- while the runner's
own RSS was 0.7 GiB. The host memory was not in our process.

### Session 10: the allocator flag is the fix, and it is a precondition

`/mnt/fast-ai/bench-results/minimax-h3-s10-20260918/`, `scripts/xpu-host-memory-probe.py` (eight
runs, under a minute each, 8 GiB placed on `xpu:0` one GiB at a time):

| Cards visible | `PYTORCH_ALLOC_CONF` | fill: host MiB per 8 GiB | copy: host MiB per 8 GiB | dma-buf fds |
| --- | --- | --- | --- | --- |
| both | unset | **+8,125** | **+7,993** | 1 |
| both | `expandable_segments:True` | +54 | +149 | 1 |
| one (`level_zero:0`) | unset | +35 | +155 | 1 |
| one | `expandable_segments:True` | +12 | +102 | 1 |

Peer residency across two visible cards mirrors device allocations into host pages unless the
allocator uses expandable segments. The fd count never moves, so it is not a leak. With the flag
set, the same run then walked straight through the phases it had never reached:

| Phase | Session 10 |
| --- | --- |
| `encode.load` | 12.64 s, 902 tensors on xpu:0, VmRSS flat at 0.778 GiB |
| `encode.forward` | 1.46 s, prompt embeds (1, 46, 5120) |
| `load.stream` | 20.61 s, 634 tensors, `rope.inv_freq` drift 0.000e+00 |
| split | block 24: 18.797 GiB on xpu:0, 18.747 GiB on xpu:1 |
| `sample` | started 11:03:53.675, **dead at 11:03:56** |

### Session 10: the fault -- and why step 4 is now blocked

Three seconds into the first denoise step, `xe 0000:03:00.0` (card2 / renderD129 = xpu:0) logged
25 copy-engine (`EngineClass: 3 bcs`) page faults, 9 CAT errors, a bcs engine reset, a timed-out
job and a device coredump; the runner died with `UR_RESULT_ERROR_DEVICE_LOST` in `scheduler.step`.
The instant it died is the instant hidden states first cross from xpu:0 to xpu:1 at the block-24
split. The stated (unproven) hypothesis is that `x.to(secondary)` is a peer-to-peer PCIe copy on
the blitter, the class this host faulted on at 2026-09-16 06:02Z, 2026-09-17 03:10Z and (ccs, via
oneCCL peer access) 2026-09-17 07:17Z.

`run_h3_t2v.py` therefore gained `B70_H3_XFER=host|direct`, default `host`: every cross-card move
is staged through a CPU tensor with an explicit synchronize on each side. Both routes are
bit-exact. `smoke_h3.sh` pins `host` for every GPU run.

**The next GPU session's first job is the host-staged smoke run** -- it is the experiment that
tests the hypothesis. It cannot run until the user picks health-probe-then-restart or reboot; see
[the fault note](2026-09-18-gpu-fault-first-light.md).

## Step 3 -- stop the service (user-authorized session script only)

Not interactively, and not by me. The live service today is unit
`fp8-service-20260918-onecard-r312d`, state `/mnt/fast-ai/bench-results/fp8-onecard-r312d-20260918/service`,
container `neural-fp8-2d712d1cee424ecabbcd8b3a1dafa204`, port 18124, status `ready`. Confirm the
package (`qwen38-27b-fp8-tp1-b70` vs `tp2-b70`) against `CURRENT.md` at session time rather than
guessing, and use the same `serve.py` that started it:

```bash
# wait for status ready (never stop a queue: that orphans its container), then stop
python3 packages/<the package that started it>/scripts/serve.py stop --state-dir "$PREV"
# then wait for status stopped, and for the stage lock to clear
```

## Step 4 -- one clip, under the watchdog

```bash
OUT_ROOT=/mnt/fast-ai/bench-results/minimax-h3 \
    timeout 5400 ./smoke_h3.sh one
```

256x448, 124 frames, seed 42. **No `STEPS=` override any more, and that is the point.** As of
2026-09-18 the step count is settled and the script picks it:

* `num_inference_steps` counts **sigma grid points**, terminal zero included, so it drives
  `steps - 1` transformer evaluations (`MiniMaxH3Scheduler.set_timesteps`,
  `scheduling_minimax_h3.py:133-136`). Every published MiniMax-H3 step count is the other kind, so
  each needs +1 here.
* The **8-step turbo LoRA is now on disk** at
  `/mnt/fast-ai/llm-models/minimax-h3-comfy/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors`
  and `smoke_h3.sh` applies it by default when the file is present, which is the **precondition**
  that makes a short run legitimate. With it, `STEPS` defaults to **9** (8 NFE, the adapter's
  distillation point). Set `LORA=` (empty) to run the base model and `STEPS` falls back to **51**
  (50 NFE, the reference runner's figure).
* There is no `guidance_scale` at any step count -- the checkpoint is CFG-distilled.

Full citations and the LoRA key mapping: [notes/2026-09-18-steps-and-lora.md](2026-09-18-steps-and-lora.md).

`smoke_h3.sh` still runs `preflight` first (MemAvailable >= 11 GiB, nothing on 18124, no running
container, venv and watchdog present) and refuses with rc 4 if any of that fails; then it puts the
run in its own process group and wraps it in `mem-watchdog.sh` at a 2048 MiB floor. First light
still asks two questions only: does this stack run on the cards at all, and does it repeat bit for
bit -- the step count being right does not make the pipeline right.

Since session 10 the script also exports `PYTORCH_ALLOC_CONF=expandable_segments:True` and
`B70_H3_XFER=host` into the run, and refuses to start while any card holds an uncleared device
coredump. **Right now it refuses**: `card2` (`0000:03:00.0`) still has one, and clearing it or
rebooting is the user's decision.

Optional, and cheap: `B70_H3_LOG_MEM=1` in the environment logs VmRSS / RssAnon / RssFile /
MemAvailable every 50 tensors through both load phases, so the real load's host curve is on the
record next to the CPU prediction.

## Step 5 -- the repeat gate

```bash
OUT_ROOT=/mnt/fast-ai/bench-results/minimax-h3 \
    timeout 5400 ./smoke_h3.sh repeat
```

Only if step 4 returned 0. Two runs, same seed, `receipt.json` hashes compared:
`video_tensor_sha256`, `audio_tensor_sha256`, `video_latents_sha256`, `audio_latents_sha256`.

## Step 6 -- health check, then restore the service with the port-free wait

```bash
for i in $(seq 1 60); do ss -ltn | grep -q ":18124 " || break; sleep 5; done
bash scripts/check-qwen36-xpu-xccl-health.sh
systemd-run --user --unit fp8-service-20260918-h3 --working-directory "$LAB" --collect \
    python3 packages/<same package>/scripts/serve.py start \
      --model-dir /mnt/fast-ai/llm-models/qwen3.8-27b-fp8 \
      --state-dir /mnt/fast-ai/bench-results/minimax-h3/service-restore --port 18124
```

The port poll is not decoration: the 02:43 restore on 2026-09-17 died on `[Errno 98] Address
already in use` because `serve.py` binds without `SO_REUSEADDR`.

---

## What a pass looks like

* **Step 2:** done -- `GO/NO-GO NUMBER` 1.663 GiB on the encoder and 0.792 GiB on the denoiser,
  `pread` loader, with the per-tensor curve flat: RssAnon returns to its baseline after each tensor
  instead of climbing, and RssFile never moves off 0.07 GiB. Re-run it if the loader changes again.
* **Step 4:** the run reaches `write` and exits 0. `receipt.json` exists with per-phase timings,
  per-card peak allocated/reserved for each phase, host peak RSS, and the four hashes. `clip.mp4`
  is 124 frames at 24 fps with audio. The watchdog log ends with `pid ... exited on its own` and a
  low-MemAvailable line that never went near the 2048 MiB floor.
* **Step 5:** all four hashes MATCH, and `compare_receipts` prints `REPEAT GATE: bytewise-equal`.
* **Step 6:** health check clean, the service comes back `ready` on 18124, `oomctl` shows no kills,
  and `journalctl -k` has no `xe` fault, CAT error, engine reset or coredump line in the window.

Then, and only then, the follow-ups: the canvas walk (320x576, 544x960, 768x1344), the step sweep,
and the two arithmetic A/Bs (`--adaln-out-dtype fp32`, `--te-rotation none`).

## Step 7 -- the second first-light candidate: `--denoiser int8`

Added 2026-09-18, after the full INT8 ConvRot denoiser finished downloading (34.04 GB, 1035 tensors,
header data end == EOF). `run_h3_t2v.py` now has a second load path for it: `--denoiser {pruned,int8}`,
env `B70_H3_DENOISER`, default still `pruned`.

**It runs after the pruned control passes, not instead of it, and not beside it.** The order is not
arbitrary:

1. the pruned path is the one whose CPU evidence is strongest (its AdaLN fit is measurably below the
   bf16 noise floor; every other weight is bit-exact against the full diffusers checkpoint), so it is
   the run most likely to tell us whether the *pipeline* works;
2. if the int8 path went first and produced a bad clip, we could not tell a broken pipeline from a
   broken dequant. With a passing pruned clip in hand, a bad int8 clip is a dequant result;
3. the int8 path is then the control that isolates the pruned AdaLN re-parameterisation -- same
   canvas, same seed, same conditioning (feed the saved `--prompt-embeds` back), one difference.

```bash
# after step 5 passes, with the cards still free:
B70_H3_DENOISER=int8 ./smoke_h3.sh one
# and the ConvRot A/B control, expected to be garbage if the rotation is real:
B70_H3_DENOISER=int8 ./smoke_h3.sh one -- --denoiser-rotation none
```

What is different about this path, and what to watch:

* **No module swap happens.** The int8 checkpoint carries the unpruned AdaLN branch
  (`time_embedder.proj_in/proj_out`, `adaln_proj.linear` 2688 -> 96768), so `time_proj`,
  `time_embedder`, every `adaln_proj` and `norm_out` stay the stock diffusers modules. Nothing from
  `make_pruned_adaln_modules` is installed. If a traceback mentions `AdaLNTableEmbedder` on this
  path, the variant plumbing is wrong.
* **Card residency is lower but the transient is new**: 16.051 / 15.650 GiB resident (split at block
  24) against the pruned form's 18.797 / 18.747, *plus* 0.484 GiB that must stay free on top. That
  transient is the largest quantized weight -- `adaln_proj.linear`, 96768x2688 int8 -- widened to
  bfloat16 for one `F.linear`, because there is no fused int8 GEMM on XPU. Worst card plus transient
  is 16.536 GiB, leaving 15.464 GiB. Comfortable, but it is a real allocation and an XPU OOM here
  would point at it first.
* **Two ConvRot group sizes are live**, 256 for the 200 attention/MLP Linears and 64 for the 50
  AdaLN projections. Both come from one file; see the rotation note below.
* **The AdaLN Linear's dtype is pinned deliberately.** diffusers calls
  `get_parameter_dtype(self.linear)` before invoking it, and a `ConvRotLinear` has no Parameters, so
  that walk lands on its first floating-point *buffer* -- the float32 scale. Left alone, the
  activation would arrive float32, the int8 weight would widen to float32 (a 1.04 GB transient, twice
  the bf16 one) and the modulation would come back float32 and promote the whole packed sequence. So
  the loader pins `compute_dtype=bfloat16` on exactly those 50 Linears, which is what the unpruned
  bf16 checkpoint does anyway. If card memory on this path looks ~2x the plan, check that pin first.

CPU evidence already in hand, before any card is touched: `./smoke_h3.sh dry` runs `--verify-remap`
for both denoisers and the ConvRot unit test. On the int8 path that is 1035/1035 checkpoint tensors
consumed, 639/639 diffusers parameters produced or substituted, 0 left over; 9 dense tensors exact
against the full BF16 checkpoint (including the two unpruned `time_embedder` tensors); and 7
quantized Linears whose dequant reproduces `W R` to within the int8 rounding floor, covering both
group sizes and the SwiGLU half swap.

## What a fail looks like, and what each one means

| Symptom | What it means | What to do |
| --- | --- | --- |
| Step 2 prints a GO/NO-GO number >= 6 GiB | the loader really does hold a large host-side footprint | **NO-GO.** Fix the loader, re-measure. Do not run on the GPU. This is not hypothetical: it is what sessions 6/7 printed, and the `pread` loader is the fix that followed. |
| Step 2's RssFile climbs with the bytes read | something re-introduced a mapping -- check `B70_H3_LOADER` really is `pread` | **NO-GO**, same rule |
| `smoke_h3.sh` exits 4 with PREFLIGHT FAIL | service, container or another lane is still resident | stop nothing yourself; the run waits for the user's decision |
| The run dies and `*.watchdog.log` has a `KILL pid=` line | **we ran out of host RAM and our watchdog caught it** -- the desired failure | record the low MemAvailable and the phase it died in; this is a loader result, not a GPU result. Do not retry unchanged. |
| The run dies with no `KILL` line and no output after `encode.load` | the 2026-09-17 failure mode repeating, i.e. something outside our cgroup | check `oomctl` and `journalctl -k`; stop the lane and write it up before anything else |
| `--denoiser int8` OOMs a card at ~2x the planned residency | the `compute_dtype=bfloat16` pin on the 50 AdaLN `ConvRotLinear`s is not taking, so the int8 weight is widening to float32 | check `load_sharded_transformer`'s `is_adaln` branch; this is a code bug, not a capacity one |
| `--denoiser int8` renders structured noise while `pruned` renders a clip | the dequant, not the pipeline -- which is exactly why the pruned control runs first | re-run `--denoiser-rotation none`: if *both* are garbage the rotation is not the variable; if only `none` is, the rotation is right and the fault is elsewhere |
| `Fault response`, CAT error, engine reset or coredump in `journalctl -k` | a GPU fault | stop issuing work, write the evidence, **do not reset the driver and do not reboot** (AGENTS.md; the 2026-09-16 fault on this host is still open). **This happened on 2026-09-18 at the first denoise step**: [fault note](2026-09-18-gpu-fault-first-light.md). |
| Step 5 prints `NOT bytewise-equal` | the stack does not repeat | **a result to record, not a reason to re-run until it passes.** Record which of the four hashes differ; `--deterministic` may fail closed on XPU, and if it does, say so instead of softening the claim to "visually identical". |
| Step 6 restore fails with `[Errno 98]` | the port poll was too short | extend the poll, restore again; the service coming back is the last obligation of the session |

Two standing rules for the whole session: one host-RAM-heavy job at a time on this host, and no
number from this lane gets promoted until quality is labelled and the repeat gate has a verdict.
