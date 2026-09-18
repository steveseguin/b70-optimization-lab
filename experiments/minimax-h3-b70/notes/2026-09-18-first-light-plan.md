# MiniMax-H3 first light, attempt 3: the exact session sequence

Date: 2026-09-18. Supersedes the sequence armed as `h3-session5-20260918` (which died with the
host, see [the stand-up note](2026-09-18-standup-prep.md) and
[the host OOM incident](../../qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md)).

The difference from attempt 2 is not the pipeline. The pipeline was never shown to be wrong -- it
never got past `encode.load`. The difference is that **the host-RAM question is now answered before
the GPU is touched, and every step has something that kills our job instead of the user's session.**

Nothing in this note has been run. Steps 1-2 are safe with the FP8 service up; from step 3 on, the
cards and the host must be free, and stopping the service is the user's decision (AGENTS.md).

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

## Step 1 -- regenerate the rotation (CPU, seconds, safe now)

```bash
cd /home/steve/b70-optimization-lab/experiments/minimax-h3-b70/scripts
/mnt/fast-ai/venvs/minimax-h3-cpu/bin/python recover-convrot-rotation.py \
    --out ../data/convrot-hadamard-256.safetensors
./smoke_h3.sh dry          # 14/14 remaps exact, 634 params from 532 tensors, 0 left over
```

`data/convrot-hadamard-256.safetensors` is not in Git (`*.safetensors` is ignored); the regenerated
file must have sha256 `ebb89aa1651e681f49461fe539bf2eb6fba0143c2733e5ad9cef438d48fb28d2`.

## Step 2 -- the CPU host-memory profile, under the watchdog (safe now, service up)

```bash
/mnt/fast-ai/venvs/minimax-h3-cpu/bin/python profile-encoder-load.py \
    --json /mnt/fast-ai/bench-results/minimax-h3/host-mem/encoder.json
/mnt/fast-ai/venvs/minimax-h3-cpu/bin/python profile-encoder-load.py --denoiser \
    --json /mnt/fast-ai/bench-results/minimax-h3/host-mem/denoiser.json
```

Both arm `mem-watchdog.sh` on their own pid at a 2048 MiB floor, in their own process group. Both
stop at 6 GiB of tensor bytes by default -- enough to see the curve, nowhere near the host limit.
Optional third run, `--drop-pagecache`, answers whether `B70_H3_DROP_PAGECACHE=1` is worth using in
the real load.

**Preliminary reading, taken while the FP8 service was up (partial, 1.8 GiB of the encoder, so NOT
the gate measurement): peak anon+file 3.114 GiB, RssAnon 1.593 GiB, RssFile 1.873 GiB.** The shape
is what a streaming loader should look like: the peak is one tensor's worth of anon plus the same
tensor's worth of page cache, and the largest single tensor in the encoder is
`model.embed_tokens.weight` at 1.556 GB. If the full pass agrees, the loader was never the problem
-- the cgroup ceiling was.

### The go/no-go rule

> **GO if the encoder profile's peak RSS + RssFile is under 6 GiB. NO-GO otherwise.**

The script prints exactly that number as `GO/NO-GO NUMBER` (`max(peak anon+file, VmHWM)`; VmHWM
catches any transient a sample missed). 6 GiB is the honest budget: the FP8 service is down for the
run, so the host has roughly 13-14 GiB available, the watchdog floor takes 2 GiB, the XPU runtime
and the rest of the process take a few, and anything under 6 GiB leaves the margin that the
2026-09-17 run did not have.

**On NO-GO the loader changes before the run does** -- dequantize and copy each Linear to the card
without ever holding a host-side copy of more than one tensor, and/or turn on
`B70_H3_DROP_PAGECACHE=1` to keep the mmap page cache down. NO-GO does not mean "try it and watch".

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
STEPS=8 OUT_ROOT=/mnt/fast-ai/bench-results/minimax-h3 \
    timeout 5400 ./smoke_h3.sh one
```

256x448, 124 frames, seed 42, 8 steps. `smoke_h3.sh` now runs `preflight` first (MemAvailable >=
11 GiB, nothing on 18124, no running container, venv and watchdog present) and refuses with rc 4 if
any of that fails; then it puts the run in its own process group and wraps it in `mem-watchdog.sh`
at a 2048 MiB floor. `STEPS=8` is still not a claim about the right step count (50 remains an
assumption). First light asks two questions only: does this stack run on the cards at all, and does
it repeat bit for bit.

Optional, and cheap: `B70_H3_LOG_MEM=1` in the environment logs VmRSS / RssAnon / RssFile /
MemAvailable every 50 tensors through both load phases, so the real load's host curve is on the
record next to the CPU prediction.

## Step 5 -- the repeat gate

```bash
STEPS=8 OUT_ROOT=/mnt/fast-ai/bench-results/minimax-h3 \
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

* **Step 2:** `GO/NO-GO NUMBER` under 6 GiB on the encoder profile, and the per-tensor curve flat --
  RssAnon returning to its baseline after each tensor instead of climbing. The denoiser profile
  lower still (largest tensor 308 MB).
* **Step 4:** the run reaches `write` and exits 0. `receipt.json` exists with per-phase timings,
  per-card peak allocated/reserved for each phase, host peak RSS, and the four hashes. `clip.mp4`
  is 124 frames at 24 fps with audio. The watchdog log ends with `pid ... exited on its own` and a
  low-MemAvailable line that never went near the 2048 MiB floor.
* **Step 5:** all four hashes MATCH, and `compare_receipts` prints `REPEAT GATE: bytewise-equal`.
* **Step 6:** health check clean, the service comes back `ready` on 18124, `oomctl` shows no kills,
  and `journalctl -k` has no `xe` fault, CAT error, engine reset or coredump line in the window.

Then, and only then, the follow-ups: the canvas walk (320x576, 544x960, 768x1344), the step sweep,
and the two arithmetic A/Bs (`--adaln-out-dtype fp32`, `--te-rotation none`).

## What a fail looks like, and what each one means

| Symptom | What it means | What to do |
| --- | --- | --- |
| Step 2 prints a GO/NO-GO number >= 6 GiB | the loader really does hold a large host-side footprint | **NO-GO.** Fix the loader (stream per Linear, `B70_H3_DROP_PAGECACHE=1`), re-measure. Do not run on the GPU. |
| `smoke_h3.sh` exits 4 with PREFLIGHT FAIL | service, container or another lane is still resident | stop nothing yourself; the run waits for the user's decision |
| The run dies and `*.watchdog.log` has a `KILL pid=` line | **we ran out of host RAM and our watchdog caught it** -- the desired failure | record the low MemAvailable and the phase it died in; this is a loader result, not a GPU result. Do not retry unchanged. |
| The run dies with no `KILL` line and no output after `encode.load` | the 2026-09-17 failure mode repeating, i.e. something outside our cgroup | check `oomctl` and `journalctl -k`; stop the lane and write it up before anything else |
| `Fault response`, CAT error, engine reset or coredump in `journalctl -k` | a GPU fault | stop issuing work, write the evidence, **do not reset the driver and do not reboot** (AGENTS.md; the 2026-09-16 fault on this host is still open) |
| Step 5 prints `NOT bytewise-equal` | the stack does not repeat | **a result to record, not a reason to re-run until it passes.** Record which of the four hashes differ; `--deterministic` may fail closed on XPU, and if it does, say so instead of softening the claim to "visually identical". |
| Step 6 restore fails with `[Errno 98]` | the port poll was too short | extend the poll, restore again; the service coming back is the last obligation of the session |

Two standing rules for the whole session: one host-RAM-heavy job at a time on this host, and no
number from this lane gets promoted until quality is labelled and the repeat gate has a verdict.
