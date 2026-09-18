# Current Workspace State

Last reviewed: **2026-09-11 15:50 UTC** (2026-09-11 11:50 EDT); the four-B70 host section below was added then.

## Authority And Update Rule

**Four-B70 host `steve-b70s`, September12:** user selected a new-model native
baseline campaign. MiniCPM5-2B setup completed, but BF16 qualification failed
the strict output-format pilot (4/6); optimization has not started. The campaign
has exited and all four cards passed postflight. No baseline is promoted. See [lane packet](experiments/minicpm5-2b-b70/README.md).
It uses a dedicated environment and original external-drive weights, with
exclusive locks and fresh processes; no permanent listener is planned. Preserve
the older queued lanes and all protected artifacts below. Actual running state
must still be checked before another launch.

This is the sole cross-repository authority for loaded service, active lane,
protected work, and immediate next actions. Verify Git status, relevant
processes, listeners, and the actual endpoint before operational changes.
Update this page when a service starts or stops; keep experiment chronology
in lane notes.

The [archived workspace ledger](CURRENT-history-20260909.md) preserves the
previous 4,577-line page verbatim. Its live-service statements and queued
actions are historical, span multiple hosts, and are not current instructions.

## Local Host And Active Review

**Four-B70 host, September 18 04:40 UTC: packet 78 launched as server 78 after two clean reloads on the new kernel/firmware (no freeze, no fault).**
Server 77b's sharded warm failed on the second clip: the host-embedding
CLIP's observation protocol (observe, encode, consume) is single-threaded
and two encode workers interleaved (`Previous embedding observations were
not consumed`). Packet 78 makes that bookkeeping per thread (numerics
untouched; CPU test), keeps the encoder shard and two-clip sampler, and
the checker allowlists the replaced parent file. Runner 78: 3-prompt warm
on the sharded arm, `pipe-samp2-tsh` 30, `pipe-samp2` 24, endurance 120.
Log `campaign-78.log`.

**Four-B70 host, September 18 04:31 UTC: packet 77 campaign done (1.515 s/clip, 16.5 fps equiv, all exact; load lock proven over 120 prompts), but the encoder shard never installed; server 77 stopped for a controlled reload as 77b (warm on the sharded graph).**
The runner's plain-graph warm clip placed the whole encoder on xpu:2 before
the shard gate ran; two encode workers on one card still overlapped. First
teardown transition on kernel 7.0.0-30 / GuC 70.44.1 with the hard-lockup
panic armed. [Results](experiments/ltx25-b70/notes/graph-capture-77-results.md).

**Four-B70 host, September 18 04:15 UTC: rebooted on kernel 7.0.0-30 with the packaged GuC 70.44.1 restored and hard-lockup panic armed (pstore erst); packet 77 launched as this boot's single server.**
Both stability levers changed together on the user's instruction after six
silent freezes on 09-17, so attribution is deferred; a further freeze now
leaves a pstore backtrace (`scripts/collect-pstore.sh`). Packet 77 = encoder
sharded across xpu:2/xpu:3 with two encode workers + two-clip sampler with
the load lock; runner 77: warm, `pipe-samp2-tsh` 30, `pipe-samp2` 24,
endurance 120. Log `campaign-77.log`.

**Four-B70 host, September 18 01:00 UTC: six silent freezes on 09-17; next boot set to kernel 7.0.0-30; packet 77 waits for it.**
Freezes hit idle, during server load, and minutes after an xe client
teardown; no backtrace exists (hardlockup_panic was 0). GuC 70.72.1 (manual,
installed 09-03) sits in BOTH initrds, so the kernel change alone does not
revert it; the GuC restore and `kernel.hardlockup_panic=1` (pstore backend
erst) were handed to the user as sudo lines. Packet 76 never ran: its text
node failed to import (`ltx_text_shard.py` was not copied); packet 77 ships
it and the generator now proves every custom node's imports resolve. The
23:57 UTC freeze zeroed 307 tracked working-tree files and a git pack;
objects recovered from a bare clone, lane files restored, bulk restore left
to the user. Runner 77: warm, `pipe-samp2-tsh` 30, `pipe-samp2` 24,
endurance 120.
[Idle freeze](experiments/ltx25-b70/notes/2026-09-17-idle-freeze-1555utc.md),
[firmware review](experiments/ltx25-b70/notes/2026-09-17-firmware-and-kernel-review.md).

**Four-B70 host, September 17 14:28 UTC: packet 76 launched (encoder sharded across xpu:2/xpu:3 with two encode workers, load lock in the fast path); firmware review done.**
Server 74b segfaulted on the fourth prompt of a 120-prompt endurance run:
both sampler workers' first clips fell through the fast path into
ComfyUI's non-thread-safe loader (module.to() under a concurrent replay);
fixed with a load lock. Firmware review: the installed GuC 70.72.1 is a
manual, upstream "testing-only" blob replacing the package's 70.44.1 (backup
on disk); the kernel moved to 7.0.0-31 on 09-05, the closest correlate of
the lockups; recommendation is to boot 7.0.0-30 first, then restore
70.44.1, then kdump. Packet 76 arms: warm, `pipe-samp2-tsh` 30 prompts,
`pipe-samp2` control 24. Log `campaign-76.log`.
[Firmware review](experiments/ltx25-b70/notes/2026-09-17-firmware-and-kernel-review.md),
[crash](experiments/ltx25-b70/notes/graph-capture-74b-endurance-crash.md).

**Two-B70 host, September 18 04:50 UTC: lc-4 PASSED every gate and is faster -- the one-card package update to the
r312d-c image is staged in the repository, the acceptance campaign is the next GPU job, and the registry push waits on
the user.** The depth-5 two-card service is back UP on 18124 (unit `fp8-service-20260918-lc4`, state
`/mnt/fast-ai/bench-results/fp8-lc4-20260918/service`), 12/12 vs the comm-2 no-MTP reference at 87.23 tok/s. lc-4 is
lc-3 re-run after two fixes in `a7fd43dcd` (the short screen runs on its baseline's own corpus; the overlay's
precondition reads `seqused_k[0]`, not `max_seqlen_k`): candidate `tp1-r312c-multiq` on the `r312d-c` image
(`sha256:ea61e698...`), one card, depth 5, 32,768 at 0.975, receipts
`/mnt/fast-ai/bench-results/fp8-lc4-20260918/` and [data/2026-09-18-fp8-lc4](experiments/qwen38-27b-b70/data/2026-09-18-fp8-lc4/).
Strict 12/12 twice (54.21 / 53.90 tok/s), ladder 64/64 three times, the 2K/8K/16K screen, the 2,048-30,720-token long
corpus in three content types, chat quality and the 21-request logprob replay all exact against the R311b no-MTP
references -- and **writing speed after a long prompt is +9.7% at 16K, +14.2% at 24K and +17.0% at 30K** (30,720:
37.5 to 43.9 tok/s), with 2K 1.4% slower, which is why the package sets `B70_FA_MULTIQ_MIN_K=4096`. lc-3's own final
service strict `rc=1` was lc-4 stopping that service mid-request three seconds after it started (container exited 0),
not a fault. **Staged in the repository, not yet measured through the launcher:** `serve.py` pins the r312d-c id with
`B70_FA_MULTIQ=1`, the overlay ships in the package, the manifest carries the toolchain and CUTLASS pin, and
`acceptance_status` is `staged-pending-acceptance-campaign`. **Next GPU job:**
`SERVICE_STATE=/mnt/fast-ai/bench-results/fp8-lc4-20260918/service CAMPAIGN_OUT=/mnt/fast-ai/bench-results/fp8-onecard-r312d-20260918 python3 experiments/qwen38-27b-b70/scripts/run-20260918-fp8-onecard-r312d-campaign.py`
(all three profiles through `serve.py`, then the service back as unit `fp8-service-20260918-onecard-r312d`). **Waiting
on the user:** `experiments/qwen38-27b-b70/docker/rebase-v0290/publish-r312d-image-ghcr.sh` (tag
`r312d-fp8-tp1-20260918`); the R311b push is still outstanding too. Earlier on this boot, session
`fp8-r312d-session8-20260918` rebuilt the multiq library twice with the cards idle, one compiler job at a time: variant
b (upstream DPC++ 2026.0.0 + IGC 2.34.4 / ocloc 26.18, 03:25-03:40) is still 8/22 exact at 7.63e-6, the same cases as
r312c, so the toolchain was never the cause; **variant c (b plus sycl-tla `87f6850`, the revision the kernel
`CMakeLists.txt` actually pins, 03:40-03:56) is bit-exact, 22/22, max abs 0.0 at both v-tile 64 and 256.** Every lab
build from r309 on had used the March `cd76379`. Nothing shipped is invalidated, but every future `_xpu_C`/GDN rebuild
must use the pinned revision. MiniMax-H3 stays off (its smoke runner no longer sets a cgroup
memory ceiling; it must never run beside a build or the service). A kernel build in a container overlapped with the MiniMax-H3 first-light run (a
27 GB text-encoder load under `MemoryMax=4G`, which thrashed instead of failing fast) on this 15 GiB host;
`systemd-oomd` killed by memory pressure up through the GNOME session to `user@1000.service` itself, so
`fp8-r312d-session6-20260918` (before its service restore), the b/c rebuild `r312d-build-bc-20260918`, the armed
`fp8-r312d-session7-20260918` and the monitors all died. No `xe` fault, both cards free, no container running. The
02:43 restore had already lost the port race (`[Errno 98]`, `serve.py` binds without `SO_REUSEADDR`). Full account,
evidence paths and the preconditions before the MiniMax lane runs again:
[host OOM incident](experiments/qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md). The user authorized restarts at
03:24 UTC and the user manager came back at 03:25, which is how session 8 ran; the rule that killed the last attempt
still holds -- one host-RAM-heavy job at a time, never beside a build. Census receipts and the variant comparison:
[`data/2026-09-18-fa-multiq-census/`](experiments/qwen38-27b-b70/data/2026-09-18-fa-multiq-census/). Still true from
earlier on this boot: the last measured service (unit `fp8-service-20260918-lc2`) was
12/12 vs the no-MTP reference at 90.52 tok/s; two-card package = allgather allreduce (90.48 tok/s, LocalMaxxing
`cmu5qk0kz07zglq01eh1opkhx`); one-card package = R311b single-checkpoint state, 32,768 default at 54.3 tok/s
(LocalMaxxing `cmu5wc2e50804lq01r0br2i5p`), max-context 40,960 (engine ceiling ~44,800 at 0.983), probes exact to
36,864 tokens. Closed: replicated drafter (never faster), two-card checkpoint state (speed-neutral). Next one-card
lever is still the multi-row verifier attention kernel, and there is still no candidate number. Git: the other host's
commit `03830fa00` pushed 302 tracked files as zero-length blobs (including `DO-NOT-REPEAT.md`); restored from
`b0c85ccc5` in `283383ed6` and local work rebased on top -- check `git diff --stat` before rebasing onto anything from
that host, whose own checkout is probably still zeroed. MiniMax-H3 (a video+audio generator, not an LLM) is halted, not
armed: `experiments/minimax-h3-b70/README.md`.

**Two-B70 host, September 17 07:50 UTC: rebooting with the user's approval after the third fault; the service needs one manual start after the boot.**
After the boot, from the repo: `nohup scripts/autolaunch-fp8-service.sh &` (health probe, then one two-card package
start on 18124; log `/mnt/fast-ai/bench-results/service-autolaunch.log`, state `service-autolaunch-<time>`), then the
strict parity against `/mnt/fast-ai/bench-results/fp8-review-20260916/tp2-mtp0-strict`. The collective A/B must not be
retried (oneCCL's peer-access kernels fault both cards); the pinned thresholds stay.

**Two-B70 host, September 17 07:25 UTC: GPU FAULT on BOTH cards during the collective A/B; port 18124 is DOWN; all GPU work halted; user decision needed (reset or reboot).**
The first server with oneCCL's default small-message kernels (`CCL_SYCL_*_SIMPLE_THRESHOLD=0`) faulted both cards two
minutes in (compute-engine page faults, CAT errors, coredumps devcd3/devcd4); the pinned-environment control had just run
cleanly at 88.50 tok/s. The fault is attributable to the experiment: those kernels use peer memory access over PCIe, the
September 14 fault class. The pinned thresholds are now documented as a guard. Third fault on this boot; the two earlier
ones were copy-engine faults on one card. Evidence `/mnt/fast-ai/bench-results/gpu-fault-20260917T0717/`. Once you
decide: health probe, then `packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start` with a new state directory.
[Findings](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md).

**Two-B70 host, September 17 07:15 UTC: two-card collective A/B running (service down for about 45 minutes, returns as unit `fp8-service-20260917k`); both FP8 records on LocalMaxxing; decode profiles done.**
Records: two cards `cmu4zwfht07nzlq01tyj03f17` (88.41 tok/s), one card `cmu53h4l407o3lq01od0vwjrr` (53.43 tok/s at
24,576 tokens). Profiles (in-worker torch/XPU traces): on one card the W8A16 GEMM is 92% of device time at about 83% of
memory bandwidth, so only the 26% of launch gaps remain; on two cards the PCIe allreduce is 47% of device time (134
calls per step at 223 µs), so the running A/B tests oneCCL's default and low-latency allreduce paths against the
pinned ring kernel, each gated against its own no-MTP reference. One-card profiles `max-context` (30,720) and
`no-quantization` (20,480) shipped and verified. Graph capture on one card disqualified. Plan for lossless 32K+ on
one card: [single-checkpoint GDN state](experiments/qwen38-27b-b70/notes/2026-09-17-gdn-single-checkpoint-plan.md).
[Findings](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md).
**Four-B70 host, September 17 13:03 UTC: rebooted by the user after the 07:00 UTC kernel stall hard-locked; LTX packet 74 launched as the single server for this boot (never to be stopped).**
The udev rule pinned all four B70s on at boot without help. The stall that
formed at 07:00 UTC (all cards pinned on, five minutes after a clean server
stop, triggered by a process that only imported torch) shows runtime PM was
necessary but not sufficient: teardown followed by a new xe initialisation
remains a lockup trigger on this kernel/driver. Rule from here: one sealed
server per boot, never stopped; no second torch process while it runs.
Packet 74 runs the two-clip sampler with explicit fills (24 prompts, ten
fixtures, per-clip oracles) then a fast+save control; log `campaign-74.log`.
[Incident](experiments/ltx25-b70/notes/2026-09-17-incident-kernel-spin-after-stop.md).

**Four-B70 host, September 17 06:52 UTC: two-clip sampler v2 launched (packet 73) after five probes established the recipe: per-clip streams, device contexts, pinned-host staged activations give 1.68x overlap bit-exact.**
Batching is closed (packet 72). Probes 1–5 (exclusive cards, block-sized
graphs): baton hand-off 0.997x, free threads on default streams 1.19x,
per-clip streams with peer copies 0.996x, explicit device contexts plus
pinned-host staging **1.68x** (ideal 1.78x), all bitwise exact. Packet 73
runs two sampler workers with a capture/replay reader-writer lock (captures
exclusive after a device drain), per-clip streams on both shard cards,
staged cross-card moves, the resident fast path and save-behind; 24 prompts
on ten fixtures with per-clip oracles, then a fast+save control. Log
`campaign-73.log`. Host stable since the runtime-PM fix (05:57 UTC).

**Four-B70 host, September 17 06:25 UTC: batch-2 route closed by proof (identical rows differ by up to 0.98); server 72 idle; next lever is the single-scheduler two-clip sampler.**
Since the runtime-PM fix at 05:57 UTC: four launches and three clean stops
with five-minute gaps, no lockup, no fault line. Packets 69–72 ran the
batch-2 row-equality proof to completion: rows differ even for identical
inputs, so batching is not bit-exact on this stack and is not pursued.
Standing position unchanged: 2.03 s per distinct clip, exact.
[Verdict](experiments/ltx25-b70/notes/graph-capture-72-results.md).

**Four-B70 host, September 17 05:57 UTC: freeze cause fixed (two B70s were runtime-suspending: boot policy raced the xe probe); all four endpoints pinned on, bind-time udev rule installed; LTX packet 69 launched.**
Eight silent lockups since 09-14 all sat on idle transitions, two on idle
boots. `0000:23:00.0` and `0000:27:00.0` had `power/control=auto` because
`b70-runtime-performance-policy.service` wrote `on` before the xe probe
finished and the probe reset it. Fix applied at 05:57 UTC (sysfs) and made
durable with `systemd/60-b70-runtime-pm-on.rules`; runners now refuse to
start unless `scripts/check-b70-runtime-pm.sh` passes, and
`scripts/check-packet-integrity.sh` refuses freeze-truncated packets (packet
68 was zeroed). Packet 69 runs the batch-2 row-equality proof; log
`campaign-69.log`. Standing position 2.03 s per distinct clip, exact.
[Cause note](experiments/ltx25-b70/notes/2026-09-17-freeze-cause-runtime-pm-race.md).

**Two-B70 host, September 17 05:30 UTC: depth-5 service is UP on 18124 (88.09 tok/s, 12/12); the night's goals are done; no GPU work running.**
Three unattended campaigns after the user chose to try the GPUs without a reset: two clean two-card starts (from idle
88.35, after one-card work 88.09, both 12/12 vs no-MTP), no new fault. One card gained two verified profiles through the
shipped launcher: `max-context` (30,720 tokens at 0.983 memory, 53.41 / 53.51 tok/s) and `no-quantization` at 20,480
tokens (51.77 / 51.78); 32K fits at depth 4 (50.97, research server). The two-card record is on LocalMaxxing as
`cmu4zwfht07nzlq01tyj03f17` (88.41). A general-text draft shortlist costs 3.6% on the suite with identical outputs (now
disclosed in the package). Graph capture on one card is disqualified (9/12). Service: unit `fp8-service-20260917f`,
state `/mnt/fast-ai/bench-results/fp8-night3-20260917/service-d`, one request at a time.
[Findings](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md).
**Four-B70 host, September 17 05:00 UTC: server 65 stopped cleanly; packet 66 (batch-2 row-equality proof) launches after the five-minute gap.**
The blocks are weight-read bound (1.57 s of the 2.03 s clip), so two clips in
one batch would read each weight once for both. That is admissible only if a
batch-2 forward is bitwise equal, row for row, to two batch-1 forwards on
this stack. Packet 66 runs that proof on the resident model (three clips,
every forward compared: original row, perturbed second row, stacked batch)
and then repeats the fast+save arm. Runner commits per arm; log
`campaign-66.log`.

**Four-B70 host, September 17 04:55 UTC: LTX packet 65 complete: 2.029 s per distinct clip, 19/19 exact (12.3 fps equivalent); server PID 22356 idle on port 8188.**
Fast path + save-behind 2.029 s; fast-path repeat 2.140 s; pipe control
2.499 s (matches packet 58); forward-timing diagnostic: 1.67 s of forwards
per clip, blocks 1.57 s, glue 0.09 s. The block region alone exceeds the
1.042 s budget, so the next lever is a single-scheduler two-clip sampler
across the shard cards, then block-level kernel work. No fault; the server
stays up idle. [Results](experiments/ltx25-b70/notes/graph-capture-65-results.md).

**Four-B70 host, September 17 04:48 UTC: LTX resident fast path lands, 2.52 → 2.135 s per distinct clip (19/19 exact, 11.7 fps equivalent); packet 65 queued.**
Packet 64 timed ComfyUI's model-management calls with every model resident:
0.42 s per clip, almost all in the transformer's call before the first
sampling stage. Skipping the bookkeeping for fully resident models (no tensor
touched) took the interval to 2.135 s on ten distinct fixtures, all exact.
The remaining arms were refused by a gate's `original` mode (now
self-restoring); server 64 stopped cleanly. Packet 65 combines the fast path
with save-behind, repeats the fast arm, runs the pipe control and the
forward-timing diagnostic; launches after the five-minute gap.
[Packet 64 results](experiments/ltx25-b70/notes/graph-capture-64-results.md).

**Four-B70 host, September 17 04:37 UTC: LTX packet 63 stopped after its diagnostic arm was refused by a guard; packet 64 launches after the five-minute gap.**
The graph-capture gate's patcher check refused the new forward-timer wrapper
(whitelist, now extended); its latch is sticky, so server 63 was stopped with
one SIGINT (3 s). Packet 64 runs the lever arms first: resident fast path
(timed, then on), save-behind, pipe control, then the forward timer last. The
runner commits after every arm. Log `campaign-64.log`.
[Packet 63 note](experiments/ltx25-b70/notes/graph-capture-63-results.md).

**Two-B70 host, September 17 03:30 UTC: GPU FAULT during the final two-card service start; port 18124 is DOWN, no GPU work running, user decision needed. Everything else tonight passed and is published.**

- **What happened:** the one-card 24K campaign finished its tests and started the two-card depth-5 service at
  03:09:38Z; at 03:10:45Z `xe 0000:03:00.0` (renderD129) raised repeated copy-engine page faults and an engine memory
  CAT error with a device coredump, about 67 s into weight load. The launcher halted the server; the runner halted
  with no restore. No reset, power change or reboot. This is the **second identical fault today** (06:02Z, same
  card, same engine, same phase: a two-card start after long one-card work). Evidence:
  `/mnt/fast-ai/bench-results/gpu-fault-20260917T0310/`.
- **Next step needs the user:** a driver reset or reboot is not mine to make. Once approved, the normal path is
  `scripts/check-qwen36-xpu-xccl-health.sh`, then one `packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start`
  (new state dir) and the strict parity check.
- **Published tonight:** two-card package at MTP depth 5 on R310 (88.32 / 88.49 tok/s pair, accepted from public
  source, was 54.8); one-card package at 24,576 tokens of context (53.43 / 53.43 tok/s, was 16,384); both one-card
  profiles passed the 64-prompt sequential oracle. CI green through commit `28c4aab9e`.
  [Findings](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md).
**Four-B70 host, September 17 04:45 UTC: three more silent lockups (03:14 UTC mid-campaign, then two idle boots); user restarted 04:11 UTC; packet 63 launched.**
Packet 62 completed two arms exact on ten fixtures before the host locked up
with no fault line: the latent upsampler's node cost is ComfyUI model
management (0.068 s per call on a resident model), not its forward (0.024 s);
capturing the forward gained nothing (2.529 s vs 2.519 s). The next two boots
locked up idle (23:40 and 23:48 EDT) with nothing running, which points at the
platform rather than the workload. No fault latch exists on this boot. Packet
63 (timed diffusion forwards, resident fast path for model management,
save-behind rerun, pipe control) runs on one server; its runner commits after
every arm because the freezes zero unflushed files. Log `campaign-63.log`.
[Packet 62 results](experiments/ltx25-b70/notes/graph-capture-62-results.md).

**Four-B70 host, September 17 03:05 UTC: LTX server 61 stopped cleanly (one SIGINT, 6 s); packet 62 launches after a five-minute gap.**
Packet 61 measured the latent upsampler's forward at 0.025 s of the node's
0.24 s (11 distinct clips exact); the remainder is model-management and
cross-device glue, so packet 62 adds a phase-timed drop-in of that node, the
captured-forward arm, a save-behind decode mode (MP4 written on the decode
worker) and a pipe control; the upsampler gate now restores itself across
mode switches. Runner `run-campaign-62.sh`, log `campaign-62.log`.
[Packet 61 results](experiments/ltx25-b70/notes/graph-capture-61-results.md).

**Four-B70 host, September 17 02:58 UTC: user-confirmed reboot after a second silent freeze; boot-03 health passed; LTX packet 61 server launched (PID 4523, port 8188).**
The previous boot froze at 00:10 UTC with only the halted DEVICE_LOST LTX
process resident (no launch pending), 43 minutes after the 23:27 UTC fault.
The user restarted the host at 02:47 UTC. Following the external-boot-health
precedent: a boot-03 admission pinned this boot, the unchanged FAULT bytes, the
2,270-record kernel prefix, runtime, packet 61 and the device properties; the
passive check and the one bounded four-card copy/compute/peer-copy probe both
passed with no new kernel records; the old fault was archived under root
review. Packet 61 now runs the latent-upsampler gate campaign (warm clip,
pipe-uptime 12, pipe-up 20, pipe control 12; log `campaign-61.log`). No
driver reset, power change or retry chain.
[Admission and receipts](experiments/ltx25-b70/data/external-boot-health-03/).

**Two-B70 host, September 17 02:45 UTC: two-card depth-5 package accepted from public source (88.32 / 88.49 tok/s pair); the new depth-5 service is on 18124 (87.76 tok/s, 12/12 vs no-MTP); one-card 24K context verified and being promoted.**
The follow-up campaign passed the one-card `no-quantization` profile's back-to-back test (64/64, strict 12/12 at
51.77), found that a 2,048-token prefill chunk lets the one-card depth-5 recipe run 24,576 tokens of context at the
same speed (32K still 0.3 GiB short), showed two-card depth 6 is exact but slower over whole answers, and replayed
the two-card package from an anonymous download of commit `5b494649f`: strict 12/12 identical to no-MTP at 88.49
tok/s, six practical requests with exact repeats, clean stop ([packet](experiments/qwen38-27b-b70/data/2026-09-17-fp8-two-card-depth5/)).
Service: unit `fp8-service-20260917`, state `/mnt/fast-ai/bench-results/fp8-followup-20260917/service`, model
`qwen38-27b-fp8`, 33,024 tokens, one request at a time. Next: the one-card 24K campaign stops it once to verify the
updated one-card launcher, then starts it again (unit `fp8-service-20260917b`).

**Two-B70 host, September 17 01:40 UTC (superseded above): review of the one-card FP8 work passed; two-card MTP depth 5 reclaimed at 88.3 tok/s; service on 18124 (depth 1, 54.71 tok/s, 12/12).**
A review campaign re-tested the shipped one-card package through its own launcher with the gate the earlier work had
skipped (64 prompts back to back plus two queued passes, all identical to no-MTP), plus strict 12/12 at 53.31 tok/s,
long prompts, the chat quality suite and a logprob replay: it holds up. Two fixes landed on the way: the launchers
now start under both Docker image stores, and the package text says 16,384 tokens of context.

- **Two cards:** on the R310 image, no-MTP matches the frozen control 12/12; MTP depths 3, 4 and 5 with the draft
  shortlist pass every gate (strict, 64-prompt oracle, 2K-16K prompts, chat quality) at 80.4 / 84.0 / **88.3 tok/s**;
  depth 1 still measures 54.90, so nothing was lost. The two-card package now ships depth 5 on R310 (`depth-1`
  profile kept); its public-source acceptance replay is the second fresh server and runs in the follow-up campaign.
- **Service:** the depth-1 R304 service was restored by the review runner (unit `fp8-service-20260916`, state
  `/mnt/fast-ai/bench-results/fp8-review-20260916/service-restored-6`). The follow-up campaign stops it once, runs the
  one-card `no-quantization` oracle, one-card context probes, two-card depth 6 and the acceptance replay, then starts
  the new depth-5 service.
- No GPU faults. [Findings](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md),
  [receipts](experiments/qwen38-27b-b70/data/2026-09-16-fp8-review/).
**Four-B70 host, September 16 23:27 UTC: GPU fault latched during the LTX pipelined-sampler arm; PID 6955 halted, no new launches possible on this boot.**
Packet 58 first delivered the corrected results on ten distinct fixtures:
serial 4.584 s per clip (12/12 exact), three-stage pipe **2.519 s per distinct
clip (19/19 exact, 9.9 fps equivalent)**. The pipelined-sampler arm then
faulted `0000:27:00.0` (page fault, devcoredump, DEVICE_LOST) on its third
clip: the second worker's graph captures ran concurrently with the first
worker's replays on the same cards. The arm is retired.
The server stays up halted as evidence; the sealed launcher refuses launches
while the boot journal carries fault lines. Next lever (latent-upsampler
graph capture, packet 60) is prepared inactive and check-only passed.
No retry, reset, power change or reboot was performed; the reboot/reset
decision belongs to the user.
[Results and incident](experiments/ltx25-b70/notes/graph-capture-58-results.md).

**Four-B70 host, September 16 23:20 UTC: LTX packet 58 server launched (PID 6955, port 8188) for the corrected ten-fixture pipeline campaign.**
The host rebooted at 17:23 UTC during Opus's packet 56 start (silent lockup, no
kernel fault line; not this session). An offline audit of the September 15-16
claims found the exactness claims hold for the boat fixture (452 clips hashed,
19 comparator passes) but every throughput prompt used one prompt and one
seed, which hid a stale-conditioning race in encode-ahead, a global-RNG race
between two sampler threads, and a confirmed stale delivery in packet 55
(parked oracle-prompt clips served as stream output). Encode-ahead now binds
to the queued next prompt's text, noise generation is serialised, reused
pipeline indices are refused, and a new driver cycles ten distinct fixtures
with a per-clip oracle. Campaign order: warm clip, serial 12, three-stage pipe
20, pipelined sampler 20; log `campaign-58.log` in the evidence root.
[Audit](experiments/ltx25-b70/notes/2026-09-16-audit-of-sep15-16-claims.md).
No power, swap, driver or reboot action; one launch, no restart chain.

**Two-B70 host, September 15 05:35 UTC: communicator NaN characterization done; user decision needed on NaN comparison.**
Stage `nan-semantics-01` completed cleanly on the newest base with no faults.
All four add formulations match XCCL on every non-NaN result at every shape and
rank; the only differences are NaN payload/sign bits, which XCCL chooses by
element position, so no fixed formula is bit-identical. Stage 05 (the IPC gate)
was not run. Continuing requires the user to accept NaN-class comparison for
this operator. No GPU work is running; port 18124 stays offline by user decision.
[NaN result](experiments/qwen38-27b-b70/notes/2026-09-15-nan-semantics-results.md).

**Two-B70 host, September 16 06:40 UTC: recovered from the fault; service back on 18124 at 54.801 tok/s, 12/12 exact.**
After the user approved a retry: the bounded XPU/XCCL health probe passed on both cards (single-device compute and
rank-to-rank allreduce), a fresh service start reached ready with no new fault, and the strict suite measured
**54.801 tok/s** with all 12 complete outputs identical to the frozen control. No driver reset, power change or reboot
was performed. Fault evidence stays at `/mnt/fast-ai/bench-results/gpu-fault-20260916T0602/`; treat the fault as a
one-off unless it repeats.

**Two-B70 host, September 16 06:05 UTC: GPU fault during a two-card service start; port 18124 is DOWN and no GPU work is running.**
`serve.py` detected the fault, halted and did not retry, exactly as designed.

- **What happened:** the one-card two-user screen finished and stopped cleanly at 06:00:11Z. The two-card service
  started at 06:00:11Z and faulted at 06:02:02Z, about 111 s in, during weight load/compile.
- **Kernel:** `xe 0000:03:00.0` (card2) Tile0 GT0, EngineClass 3 (copy engine): repeated
  `Fault response: Unsuccessful -EINVAL`, then `Timedout job ... in python3`, then a device coredump. No reset,
  recovery or wedged line followed.
- **State now:** no containers, no GPU processes, no driver reset, no reboot, devcoredump still present.
- **Evidence:** `/mnt/fast-ai/bench-results/gpu-fault-20260916T0602/` (kernel log, journal window, states, summary).
- **Next step needs the user:** faults halt work, and a driver reset, power change or reboot is not mine to make.
  A bounded XPU/XCCL health probe is the normal first check once approved.

**Two-B70 host, September 16 00:30 UTC: one-card FP8 packet published; R310 kernel fix replaces the head-group overlay; service back on 18124.**

- **New packet** `qwen38-27b-fp8-vllm-tp1-b70`: package, recipe, 7 measured graphs. It replaces
  the August one-card eager entry, now marked replaced.
- **Image** R310 `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb816507…`: R304
  plus the oneDNN r309 one-card shapes and the kernels r310 GDN output fences.
- **Recommended** (MTP depth 5, INT4 draft shortlist, 13,824 context): 53.45 / 53.55 tok/s on
  two fresh servers, prefill 1,987-2,043 tok/s at 2K-12K.
- **No-quantization profile:** 51.6 tok/s at 12,544 tokens. No MTP: 19.4 tok/s.
- **Checks:** every depth 3-6 and both draft heads are 12/12 identical to no MTP. The context
  screens, the chat quality suite and a 21-request logprob replay are all exact.
- **Package test:** `serve.py` pulled the published image and passed strict 12/12 for both
  profiles, with clean stops.
- **Site checks:** validators and tests pass. `check-pinned-hashes` still reports the 231
  historical Flash-Next drifts from before this work.
- [Final measurements](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-package-results.md).

**Two-B70 host, September 15 20:50 UTC: one-card FP8 broad matrix, no-quantization draft option, chat quality parity; GPUs in use by research queue.**

- **Depths 3-6 with both determinism overlays:** all 12/12 strict and
  context-screen identical to MTP0.
  - No single metric decides: depth 6 leads early and long-context decode, depth
    4 leads whole answers, and depth 5 stays the balanced default (53.40 tok/s).
- **Draft-only INT4 shortlist head:** worth 20-25% over FP16 shared-head
  drafting.
- **FP16 67k-row draft shortlist (`b70_draft_fp16_shortlist`):** removes all
  quantization. 51.86 tok/s, needs 0.975 memory for a 12,544 context.
- **Chat-mode quality suite** (exact answers, JSON, repeat hash, 7.6K needle):
  depth 5 with either head matches MTP0 exactly.
- **Queued:** R310 kernel build with global memory fences in the GDN output
  kernel, then a 200-repeat census. Its goal is to replace the head-group
  overlay. The two-card service is stopped for this and will be restored
  afterwards.

[Matrix note](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-depth-draft-matrix.md).

**Two-B70 host, September 15 18:30 UTC: one-card FP8 made deterministic and long-context exact (two overlays); service back on 18124 (54.705 tok/s, 12/12 vs control).**
Broader tests found two one-card-only issues the short strict suite missed.

- **GDN prefill:** identical prompts changed logprobs on every repeat, because
  the XPU chunked delta-rule output races with 48 value heads (7-71 of 200
  repeats at 1K-8K tokens; TP2 24 heads 0/200, and the TP2 service replay is
  bitwise stable).
- **Long-context verify:** depth-5 verifier attention rows differ from decode
  once key length exceeds 1,984 (FA2 census), flipping a near-tie after a
  12,288-token prompt.
- **Fixes:** research overlays `b70_gdn_head_groups` (delta rule in 2×24 head
  groups) and `b70_fa_verify_rows` (verify rows as decode calls above 1,536
  keys).
- **Result:** R309 depth 5 + shortlist at 13,824 context is 12/12 strict and
  18/18 long-context continuations identical to MTP0 on two fresh servers, at
  53.40 tok/s (unchanged), prefill 1,340/1,979/1,947 tok/s at
  512/2,048/12,288.
- **Also fixed:** the embed plugin's dead 2.37 GiB host copy.

[Notes](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-gdn-prefill-nondeterminism.md).

**Two-B70 host, September 15 16:10 UTC: one-card FP8 depth 5 made exact (R309); 53.5 tok/s lossless; service back on 18124.**
The one-card depth-4/5 answer changes came from the oneDNN W8A16 fixed-K gate
(r137a), which covered only TP2 per-rank shapes; a new census showed full-width
rows identical only for M=1-4. Patch r309 adds the five one-card shapes; the
local image R309 (R304 + rebuilt kernels, `7d3219a0`, not pushed) makes M=1-16
identical. On one card, depths 3/4/5 are now 12/12 against R309 no-MTP. Depth 5
with the existing 67k draft shortlist measured 53.602 / 53.463 tok/s on two
fresh servers at 11,264 / 13,824 context (was 46.9 at depth 3). Depth 6 gave
54.6 once, with a lower full-answer rate. No kernel faults. The two-card service
still runs R304 and was restarted afterwards (state `service-after-r309`): 54.767 tok/s, 12/12 identical to the pre-test control.
[R309 results](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-r309-depth5-exact.md).

**Two-B70 host, September 15 14:45 UTC: FP8 runs on one B70 (46.9 tok/s lossless); cold-start fix restores 54.8; service on 18124.**
The earlier 54.3 restore readings were a first-request cost: a fresh server
JIT-compiles two MTP draft kernels during the strict suite's first prompt.
`serve.py` now sends one untimed warm-up completion before ready; the restored
service (`final-service-warmup`) measured 54.762 tok/s cold, first prompt 56.54,
12/12 outputs identical to the pre-test control. Official FP8 on one card: a new
lossless host-embedding plugin frees 2.37 GiB, and compiled serving then gives
MTP0 19.3, MTP1 32.5 (20,480 context) and MTP3 46.9 tok/s (16,384 context), all
12/12 identical across fresh servers and to MTP0; MTP4/5 reach 49.7/51.7 but
change three answers and are not qualified. No kernel faults. Research launcher
only; no one-card package yet.
[One-card results](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-results.md),
[warm-up fix](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-cold-start-warmup.md).

**Two-B70 host, September 15 13:30 UTC: qualified FP8/MTP1 service restored on 18124 and matched pre-test quality and speed.**
The unchanged R304 FP8 TP2/MTP1 service (image `7cd7bb16`, helper state
`/mnt/fast-ai/bench-results/optimization-validation-20260915/restored-service`)
is ready at `http://127.0.0.1:18124/v1`, model `qwen38-27b-fp8`. Strict check:
12/12 complete outputs match the pre-test reference, canaries pass, cache zero,
54.306 tok/s versus 54.855 control (-1.0%, within session drift; the September
14 post-reboot restore measured 54.316). Context profile: all 18 continuations
exact; prefill 2,861/3,670/3,296 input tok/s at 512/2,048/16,384 versus
2,859/3,677/3,305 before. No kernel faults. Today's stopped test containers were
removed after their receipts were saved; incident containers are kept.
[Restore results](experiments/qwen38-27b-b70/data/2026-09-15-post-test-restore/),
[community cookbook claim review](community/sergiiob-b70-inference-cookbook/validation/2026-09-15-qwen38-engine-comparison-review.md).

**Two-B70 host, September 15 13:10 UTC: both transfer optimizations validated; neither is worth adopting; GPUs idle.**
Exact two-card communicator stage 05 passed every quality case at 1/2/512/4,096
rows under the user-approved NaN-class rule, with peer IPC, clean retirement, no
kernel faults, a clean memory guard and container exit 0. Paired operator timing:
153% and 124% slower at 1 and 2 rows (decode), 30% slower at 512 rows, 8.2%
faster at 4,096 rows (5/5 blocks). The gain covers only long-prompt chunks, is
about 1% of prefill before integration copies, and decode gets slower, so XCCL
stays. The metadata tweak (earlier entry) is exact but speed-neutral and stays
off. No GPU work or service is running; port 18124 remains offline by user
decision and can be restored on request.
[Communicator results](experiments/qwen38-27b-b70/notes/2026-09-15-exact-comm-nan-results.md),
[metadata results](experiments/qwen38-27b-b70/notes/2026-09-15-metadata-tweak-results.md).

**Two-B70 host, September 15 12:55 UTC: user approved NaN-class comparison; communicator stage 05 running.**
The user chose to count any two NaN outputs as equal for the exact two-card
communicator; every other bit must still match XCCL. Under that rule all four
formulations match the saved characterization, and stage 05 runs the Native04
arithmetic (`m0`) on the newest base: exact checks at 1/2/512/4,096 rows, then
alternating XCCL-versus-candidate timing, under the memory guard and fault
monitor. It uses peer IPC, the path that coincided with the September 14 fault.

**Two-B70 host, September 15 12:40 UTC: communicator NaN characterization done; stage 05 awaits a user decision on NaN comparison.**
`nan-semantics-01` completed cleanly on the newest base (no faults, guard clean,
exit confirmed). No fixed add formulation matches XCCL bit for bit: every
mismatch is NaN versus NaN with a different payload or sign, XCCL's choice
depends on element position, and all real numbers and infinities matched.
Stage 05 is not admitted under the bit-exact NaN rule. It could continue only if
NaNs are compared as a class; that oracle change is the user's decision. No GPU
work running; same boot `b13caae3`.
[NaN results](experiments/qwen38-27b-b70/notes/2026-09-15-exact-comm-nan-results.md).

**Two-B70 host, September 15 05:25 UTC: metadata tweak validated exact but speed-neutral; exact communicator tests next.**
On the newest base (`506fcc26`) the unchanged server matched all 12 reference
outputs, the native gate passed 36 cases on both GPUs, and four alternating
normal/tweak rounds all matched exactly with zero cached tokens. Writing speed
54.245/54.392/54.450/54.543 tok/s and reading speeds within 0.4% show no gain
beyond control drift; the tweak stays off. Research server 18129 is being
stopped once. Next: the no-IPC NaN characterization (`nan-semantics-01`) for the
exact two-card communicator on the same image, then its stage-05 gate only if a
single add formulation matches XCCL. Port 18124 stays offline by user decision.
[Results](experiments/qwen38-27b-b70/notes/2026-09-15-metadata-tweak-results.md),
[communicator preparation](experiments/qwen38-27b-b70/notes/2026-09-15-exact-comm-fixes.md).

**Two-B70 host, September 15 04:50 UTC: after restart, allocation diagnostic confirmed the OOM cause; metadata research server starting on 18129.**
The user restarted the host (boot `b13caae3`); the bounded health check passed
with no kernel faults. A no-model 2 GiB allocation on the newest image reproduced
the research-launch memory problem at small scale: with both GPUs visible and no
`PYTORCH_ALLOC_CONF`, driver-held host memory grew 2.05 GiB; with
`expandable_segments:True` it grew 0.06 GiB, and with one GPU 0.13 GiB. No GPU
faults. The research launcher now adds the five qualified environment variables
and starts a root host-memory guard that kills the container cgroup without
Docker (live-tested on a throwaway container). The metadata research server is
starting on localhost18129; the preregistered client campaign follows. Port
18124 stays offline by user decision. The exact two-card communication fixes
are being prepared offline. Evidence:
`/mnt/fast-ai/bench-results/optimization-validation-20260915`;
[diagnostic summary](experiments/qwen38-27b-b70/data/2026-09-15-newest-base-alloc-diagnostic/summary.json).

**Two-B70 host, September 15 03:00 UTC: user decision — validate the optimizations on the newest base; the service can wait; host restart pending.**
The user set the goal to validating the transfer optimizations, not restoring
the API. Decisions: (1) run the metadata tweak campaign on the newest upstream
base (`506fcc26`) after fixing its launch environment; (2) fix the exact
two-card communication prototype offline (NaN operand selection versus XCCL,
abrupt-exit retirement), then test it on the cards. The user will restart the
host to clear the GPU fault. After the restart, in order: bounded health check;
research launcher environment fix plus a host-memory watchdog; a small no-model
allocation diagnostic on the newest image; the full metadata campaign; then the
communicator fixes, a no-IPC NaN characterization and its native exact gate.
Any GPU fault halts the work for review; no retries. DFlash stays excluded.

**Two-B70 host, September 15 02:20 UTC: GPU fault during FP8 restore; GPU work halted, API offline, reboot decision needed.**
The bounded standard health check passed on both cards at 01:58 UTC. Loading
the unchanged qualified R304 FP8/MTP1 service in `final-service` then faulted
card 0000:e3:00.0 at 02:00:38 UTC as target weights finished loading: 33
unsuccessful copy-engine (bcs) page-fault responses, 8 engine memory CAT errors,
a bcs engine reset, a timed-out job and a device coredump. The helper halted and
stopped once; the container is gone, no model process owns the GPUs and port
18124 is closed. The campaign `FAULT.json` latch is set and the campaign is
closed; the metadata change remains unvalidated. Same boot; no retry, reboot,
driver reset or settings change by the agent. **Restoring the service needs the
user's decision on a host reboot**; afterwards use a newly admitted recovery
root (health check, qualified service, full strict check). Cause not
established; a swap-out burst preceded the fault by seconds. The research
launch's missing environment variables (see the entry below) do not explain
this fault; the restore carried them.
[Fault note](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-restore-gpu-fault.md).
This supersedes the restore statement below.

**Two-B70 host, September 15 02:00 UTC: research server ran the host out of memory during load; restoring original FP8 service.**
The newest-base V1/native-MTP control on localhost18129 (image `506fcc26`,
upstream `dc36fcce9`) never became ready and served no requests. From about
19:40 UTC its model load exhausted host RAM: the root filesystem stalled, the
owner's monitor blocked and could not stop it, and after about four hours the
kernel OOM killer ended the desktop session, login-screen processes and one vLLM
worker. The container exited at 00:39 UTC (Docker OOMKilled). About 12.7 GiB was
held outside normal memory counters; worker allocations failed inside xe dma-buf
export. No xe memory fault, CAT error or engine reset was recorded; memory has
recovered and no model process owns the GPUs. Same boot; no reboot, driver
reset or settings change. The metadata client never ran. Do not relaunch
that research recipe unchanged: it and the 09:27 freeze candidate omitted five
qualified environment variables, including
`PYTORCH_ALLOC_CONF=expandable_segments:True`; the launcher now refuses. Next:
one bounded standard health check, then
restore the qualified R304 service on 18124 in `final-service` and repeat the
full strict output check.
[Incident note](experiments/qwen38-27b-b70/notes/2026-09-15-research-load-host-oom.md).
This supersedes the loading statement below.

**Two-B70 host, September 14 19:27 UTC: recovery qualified; metadata research loading.**
The original FP8/MTP1 service passed all12 complete frozen-reference outputs,
canaries and cache-zero checks at54.0136 output tokens/s. Its planned graceful
stop completed with no owners and no new GPU fault. Loading the separate
reviewed V1/native-MTP control on localhost18129 for metadata validation.
Port18124 is temporarily offline during this planned test. No custom
communicator, DFlash, target-arithmetic change or quality waiver is enabled.
Same boot; no reboot/reset or host settings changes. The original service will
be restored after the bounded comparison if device health remains clean.
[Recovery and metadata plan](experiments/qwen38-27b-b70/notes/2026-09-14-fp8-recovery-metadata-plan.md).
Raw root: `/mnt/fast-ai/bench-results/fp8-mtp-recovery-metadata-20260914`.
The prior incident entry below remains historical evidence of the halted run.

**Two-B70 host, September 14 18:36 UTC: GPU work halted after exact-TP2 probe fault.**
The corrected communication probe passed 12 finite/edge cases per rank, then
failed exact NaN-payload parity. At 18:30:41 UTC the kernel also recorded BCS
memory faults on both GPUs, a CAT error and driver-initiated engine resets.
The controller preserved the fault latch and confirmed container exit; no
subsequent GPU request or model reload occurred. The causal relationship to
IPC cleanup/process exit is unproven. Do not retry this probe or start a model
under the current faulted campaign. Offline analysis and the failed-attempt evidence packet are complete.

Read-only postflight at 18:36 UTC: no render-device owners, no running Docker
containers, both 18124 and 18129 closed, same computer boot. GPU compute health
has not been requalified. The original service was stopped once at 18:07 UTC for
the planned exclusive test; the API is currently unavailable. No agent reboot,
driver reset or power/memory-setting change occurred.

Metadata relocation passed 36 offline cases on both source versions; its native
and endpoint gates remain unrun. The separate V1/MTP control image is built but
unqualified. No speed measurement or optimization is promoted. Preserve
`/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914/FAULT.json`, all four
operator-stage snapshots and the earlier unrelated freeze packet below.
[Implementation results and incident](experiments/qwen38-27b-b70/notes/2026-09-14-mtp-lossless-transfer-results.md),
[implementation plan](experiments/qwen38-27b-b70/notes/2026-09-14-mtp-lossless-transfer-plan.md),
[earlier review](community/1337hero-r9700-qwen38-radiance/validation/2026-09-14-mtp-fp8-transfer-review.md).

**Four-B70 host, September15 05:25 UTC: clip 6.415 -> 4.682 s, all exact; GPU work paused for a reboot.**
Qualified position (packet21, `prepared-encoder-graph-capture-21`, manifest
`d515527a6f7eb1277df5f354a46522e6da1597b73fca08a91519caee70fa5498`): warm clip
preview **4.682 s** against a 6.415 s control, sampler **1.942 s** at **1.86x**,
video decode **0.560 s**, text encode unchanged at 1.741 s. Thirteen clips,
**every one bytewise identical** on images, video latent, audio latent and
waveform, at 256x256, 25 frames, 24 fps, native BF16, 8+3 steps. Two independent
exact changes: per-block `torch.xpu.XPUGraph` capture of the 48 transformer
blocks, and the already-qualified axis-cache decoder.
[Result](experiments/ltx25-b70/notes/graph-capture-21-results.md).

**Paused:** packet22 tried to extend graph capture to the video decoder. It was
blocked by a single host read of tensor contents used as a shape
(`int(en.max())`), which returns garbage inside a capture and asked the allocator
for 1,044,902 GiB. Abandoning the capture left a GPU **CAT error and engine
reset** on one card. The driver recovered and the host is up with all four render
devices free, but the sealed launcher greps the whole boot journal for device
faults and will now refuse every launch on boot `831530c8`. **A reboot is needed
before GPU work resumes**; nothing else is blocked.
[Analysis and the one-line fix](experiments/ltx25-b70/notes/vae-graph-capture-blocked-01.md).

Earlier on the previous boot, two spontaneous `xe` GuC hard lockups occurred, the
second of which froze the host; the first ran ordinary eager clips before graph
capture existed, so it is not attributable to this work.
[Incident](experiments/ltx25-b70/notes/xe-lockup-incident-01.md).

**Four-B70 host, September15 03:30 UTC: first exact LTX speedup landed; sampler 1.83x.**
Per-block `torch.xpu.XPUGraph` capture of the 48 native transformer blocks cuts
the sampler from 3.669 s to 2.001 s and the warm clip from 6.459 s to 4.792 s,
with **all ten campaign clips bytewise identical** on images, video latent, audio
latent and waveform. Checkpoint, precision, 256x256, 25 frames at 24 fps and the
original 8+3 sampler schedule are unchanged. Packet
`prepared-encoder-graph-capture-19`, manifest
`e378498bb183982c59a76c366efc8d9e39f0197c747fb01e176299ab05ae84c7`, server
`encoder-server-graph-capture-19` (PID22639) on user-reboot boot `64bbd5d2`.
Each of the 96 graphs is proven bit-identical to a fresh eager execution of the
same block before it is used, and proven non-inert. See
[the result](experiments/ltx25-b70/notes/graph-capture-19-results.md) and
[why the clip was dispatch-bound](experiments/ltx25-b70/notes/dispatch-bound-diagnosis-01.md).

Two candidate levers were **retired on evidence** rather than pursued: the
transformer output-column partition (the linear layers already run at the
537 GB/s copy roofline, so it attacked the wrong term) and whole-model
compilation (the lane's own all-48 screen is exact but 0.93 s *slower* in the
sampler). Packet13's text-encoder full residency is exact and speed-neutral;
it is kept as the base because it removes a per-request growing CPU offload.

The sampler is now GPU-bound: 77.6% of profiler samples wait on the model call,
the adapter's own Python is ~12%, and per-step cost finally scales with token
count (165 ms at 64 tokens, 224 ms at 256) where eager barely did. The next
structural inefficiency is that **only one of four B70s computes at any instant
during sampling**: blocks 0-20 run on XPU0, then 21-47 on XPU1, strictly
serially, while XPU2 and XPU3 sit idle. No reboot, driver reset or
power/memory setting change was made.

**Four-B70 host, September14: packet12 idle after safe memory refusal.**
LTX PID11888/exec40923 remains healthy and idle at `http://127.0.0.1:8188`,
packet12 manifest`b29b750c31feda9d4be7fdc768e876a1f5d58ad11a699022b1d8ae6bdaa59666`.
Screen02 client/exec12642 exited1: five control clips passed all four raw
oracles, then the first encoder transition refused replacement construction.
After full old-encoder weakref/registry release, available RAM was46.58GiB,
below the unchanged56.89GiB construction floor. Diffusion/VAEs/upscaler stayed
owned. No replacement encoder was allocated. Requests halted; no retry/reload.
Postflight: same user-reboot boot5414a640, empty queue, only11888 owns renders,
no FAULT latch and no new kernel entries. No agent reboot/reset/settings action.
Preserve the failed screen; it does not qualify host timing or full transitions.
Terminal evidence is exported (325 text files, exact archived hashes).
Next: keep a fixed encoder mode for later sampler work; separately design
private ownership reuse without checkpoint/constructor allocation. The next
sampler candidate is a two-stage, same-device full-N versus half-N Linear
exactness diagnostic; its new adapter needs source review before any reload.
Existing constructor floor and all quality gates remain unchanged.
[Postflight](experiments/ltx25-b70/data/host-embedding-screen-02-postflight.json).

**Historical Four-B70 host, September14 19:32 UTC: bounded post-reboot health assessment passed.**
One diagnostic (parent8068/worker8088) passed four exact copy/compute checks and
twelve directed BF16 copies on the expected ordinal UUIDs. Both exited0;
locked passive postflight confirmed released render nodes and no new kernel
faults. No agent reboot/reset or host settings change. The root operator
archived the old-boot FAULT byte-for-byte after separate evidence review;
the prior failed model campaign remains invalid. LTX is still stopped.
The guarded tiny CPU qualification then passed all six cases (child8812,
exit0): actual encoder/registry release, exact CPU output and memory-refusal
ordering; both GPU backends stayed uninitialized. Parent postflight was clean.
Next: successor runtime/client preparation and cold-assembly RAM review.
Large model transitions, full clip performance
and endurance remain unqualified; a new fault halts requests.
[Health result and admission](experiments/ltx25-b70/data/external-boot-health-02/recovery-admission.json).
[CPU lifecycle result](experiments/ltx25-b70/notes/host-embedding-resident-lifecycle-native-01.md).

**Historical four-B70 state, September14 19:20 UTC: user-reported freeze and user-confirmed reboot.**
The computer is now on boot `5414a640-c223-4a67-baa2-ec2f4c4c5917`,
started about19:12 UTC. The user confirms restarting it after a freeze; the
agent did not reboot or reset it. LTX remains stopped and the original FAULT
latch remains byte-identical. The planned same-boot health diagnostic never
ran (its one-use output directory is absent); its old-boot admission is invalid.
Passive checks find unowned render nodes and no detected current-boot kernel
fault. These observations do not qualify GPU health. A new, separately reviewed
bounded assessment is being prepared; no model or native CPU tests are admitted.
The previous boot's kernel tail contains the earlier18:13 xe fault; it does not
establish the cause or precise time of the later reported freeze.
[Passive incident evidence](experiments/ltx25-b70/data/user-reported-freeze-02/report.json).

**Historical four-B70 state, September14 18:13 UTC: LTX stopped after host OOM and xe fault.**
Linux OOM-killed LTX PID116013 at18:12:58 UTC during the third component
transition (host-table back to control), before the next clip completed.
Exec15201 exited137. Xe GPU0 reported a bcs engine fault/reset at18:13:01,
after the process kill. Client116455/exec91667 exited1 and submissions halted.
The root FAULT.json now records the incident; no new native GPU/CPU work.
No automatic reboot, driver reset, application restart or settings change.
The computer remains on the same boot; passive postflight is preserved below.

Ten completed clips passed all four raw oracles, including all five host-table
clips with full remaining encoder residency. Host warm previews6.322–6.455s
versus first-control6.378–6.576s; the final control is missing, so this is an
incomplete screen and no speed promotion. The failed export and memory audit
are preserved. An inactive successor retains diffusion/VAEs/upscaler across
encoder changes, requires old encoder owner release, and checks separate
restore/construction RAM budgets. Ten stdlib fake/header-only tests and an
independent source review passed. Actual CPU lifecycle qualification, a new
packet/client and native testing remain pending under the fault latch. Its
memory guards cover encoder transitions, not initial diffusion construction.
[Transition fix](experiments/ltx25-b70/notes/host-embedding-clip-only-transition-01.md),
[memory audit](experiments/ltx25-b70/notes/host-embedding-transition-memory-audit-01.md).
The separate C++ CPU v8 cache-policy proposal is also source-only and inactive.
Keep successful raw parity evidence and all failures.
[Incident postflight](experiments/ltx25-b70/data/host-embedding-screen-01-incident/postflight.json).

The earlier four-B70 entries below are historical snapshots; the fault state
above supersedes their live-process and pending-launch statements.

**Four-B70 host, September14 18:07 UTC: packet11 ready; encoder comparison starting.**
LTX PID116013/exec15201 serves `http://127.0.0.1:8188`, using
`prepared-encoder-host-embedding-11` at manifest
`34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08`.
All four startup device checks, strict determinism, complete endpoint identity
and both new node interfaces passed. Same computer boot, no host/settings action.
Client PID116455/exec91667 runs the bounded15-clip `host-embedding-screen-01` comparison, with original
transformer/decoder and all four raw oracles. No GPU quality/speed claim yet.
[Startup admission](experiments/ltx25-b70/data/host-embedding-migration-11/startup-admission.json).

**Four-B70 host, September14 18:05 UTC: controlled LTX application migration.**
Packet10 PID84255/exec33936 exited0 after one SIGINT to load reviewed packet11.
The computer is on the same boot; no host or memory/power settings action.
Packet11 manifest34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08
passed CPU integration, source assembly, builder and startup offline gates;
the independently reviewed15-clip client passed10 stdlib checks and source
admission. Starting the application and verifying registration precede all clips.
[Migration evidence](experiments/ltx25-b70/data/host-embedding-migration-11/preflight.json).

**Four-B70 host, September14 17:54 UTC: actual CLIP integration CPU gate passed.**
The inactive host-table adapter passed all six actual tiny CPU CLIP integration
groups, including unchanged memory estimation/native owner loading, clone and
state lifecycle, byte-exact encoding, bounded metadata observations and inference
tensors. PID112132/exec53199 exited0; both GPU backends remained uninitialized.
The resident component assembly also passed nine stdlib lifecycle/source tests.
Full-model GPU residency, original four-output clip parity and speed remain
unqualified. Packet11 and its comparison client are being prepared offline;
packet10 PID84255/exec33936 remains the live application. No reload or host
settings action occurred. The17:54 postflight found the same full identity,
empty queue, only84255 on all four render nodes, and no faults.
[CPU evidence](experiments/ltx25-b70/data/host-embedding-integration-postflight-01.json).

The separate C++ CPU v7 fixture installed the reviewed virtual CPU registry and
completed one eager call. Its first compile halted at the retained CUDA
current-device trap in AOT cache system metadata; no compiled result or C++ call
completed. Both GPU backends remained uninitialized. Preserve the refusal;
no unchanged retry. This does not block the encoder comparison.
[V7 result](experiments/ltx25-b70/native-cpp-block-01/guarded-v7-result-01.json),
[postflight](experiments/ltx25-b70/native-cpp-block-01/guarded-v7-postflight-01.json).

**Four-B70 host, September14 17:34 UTC: encoder CPU proof passed; application unchanged.**
The CPU embedding candidate passed all six actual-source groups: raw-byte
token/embedding equality, named-owner loading, clone/detach/restore, inference
storage, mutation refusals and installation rollback. PID107471/exec35632
exited0 with both GPU backends uninitialized. This is a tiny CPU fixture proof;
GPU residency, full-clip equality and speed remain unmeasured. Next: inactive
CLIP/runtime integration with explicit CPU and encoder ownership, followed by
native gates. [CPU results](experiments/ltx25-b70/notes/host-embedding-cpu-v3-results-01.md).

Packet10 PID84255/exec33936 remains healthy and idle with the same full endpoint
identity, empty queue, sole ownership of all four render nodes and no fault.
Saved-event attribution puts about1.82s in encoding and3.54s in the two sampler
nodes. A new inactive CPU embedding ownership candidate could free1,920MiB of
encoder VRAM and replace465MiB of recurring weight uploads with7.5MiB of token
rows. Native correctness/residency and speed are unmeasured; unchanged memory
reserve and full actual residency remain required. Source review caught and
corrected named-owner loading and inference-tensor version assumptions.
[Candidate](experiments/ltx25-b70/notes/host-embedding-gather-candidate-01.md),
[review](experiments/ltx25-b70/notes/host-embedding-source-review-01.md).

The guarded C++ CPU v6 diagnostic verified PyTorch's built-in CPU detection
disable setting and completed one eager call. Generic Dynamo torch-function
handler registration still enumerates device interfaces; the first compile
halted at that retained trap. Both GPU backends stayed uninitialized; no
compiled C++ qualification yet. A future explicit CPU device-registry policy
needs source review; no unchanged retry is scheduled. Encoder integration
continues independently. No live application or host action occurred.
[V6 refusal](experiments/ltx25-b70/native-cpp-block-01/guarded-v6-native-attempt-01.md).
Unconditional cross-step text K/V reuse was rejected from the actual checkpoint
and source: ADaLN changes the projection inputs with timestep.
[Audit](experiments/ltx25-b70/notes/cross-step-text-kv-audit-01.md).

**Four-B70 host, September14 16:57 UTC: decoder confirmation complete; scoped gain retained.**
All18 balanced `na-axis-confirm-01` clips passed the four original raw-output
oracles and full24-call decoder checks on unchanged packet10 PID84255/exec33936.
Across this screen and confirmation,29/29 clips are exact. All six balanced
decoder comparisons favor the cache, median−83.231ms. Whole-preview effects
split3wins/3losses, median−41.966ms; preview medians remain about6.4s. Retain the
local decoder gain, with no overall speed promotion or streaming qualification.
Client31882 exited0; same boot, queue empty, onlyPID84255 owns all four render
devices, no fault. Default route is original; private axis-cache remains
available. No reload was required for confirmation. Next: saved-event attribution
of encoder/sampler variation and the remaining transformer/encoder costs.
[Confirmation results](experiments/ltx25-b70/notes/na-axis-confirm-01-results.md).

**Four-B70 host, September14 16:42 UTC: decoder screen passed; small speed gain to confirm.**
PID84255 serves `http://127.0.0.1:8188` in exec33936, packet
`prepared-encoder-na-axis-10`, manifest
`d6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a`.
Four startup device checks, strict determinism, full identity and private decoder
node registration passed. Packet09 PID82046 exited0 after one SIGINT following
the reviewed source-pin correction; same computer boot and no fault recorded.
All11 `na-axis-screen-01` clips passed full original four-output raw parity;
nine scoped decodes passed the complete24-call sequence and owner/config checks.
Cache previews6.297–6.446s; median paired changes −119.528ms preview and
−83.436ms decoder. Client80638 exited0; queue empty, no fault, original dispatch
and default NA route. This is a screening gain, not a promotion or streaming
qualification. Next: preserve terminal evidence and prepare a balanced18-request
confirmation on this same application. No reload is required. Halt submissions
on failure without cycling the service.
[Screen results](experiments/ltx25-b70/notes/na-axis-screen-01-results.md).
The separate guarded CPU compiler probe exited1 after blocking an import-time
`torch.xpu.device_count` query; XPU stayed uninitialized, no model/compile calls
occurred, and LTX PID84255 remained idle and healthy. It did not reach the earlier
cache-metadata hypothesis. No retry is scheduled during confirmation.
[Guarded probe](experiments/ltx25-b70/native-cpp-block-01/guarded-v2-native-attempt-01.md).
[Corrected preparation](experiments/ltx25-b70/notes/na-axis-runtime-10-prepared.md).
This supersedes all older PID/startup statements below.

**Four-B70 host, September14 16:33 UTC: packet09 node startup rejected; zero clip requests.**
PID82046 serves `http://127.0.0.1:8188` (exec49702) with an empty queue.
All four startup device checks passed and strict determinism is enabled, but
`LTXNAAxisDecode` failed registration before router installation: its sd.py pin
incorrectly names the upstream source rather than the inherited encoder source.
No native campaign was launched, and no automatic retry follows. Preserve this
idle application and packet09 while correcting the source integration offline.
Old PID66846 exited0 after one SIGINT; computer boot remains
`8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a`, no host reboot or settings changes.
[Startup failure evidence](experiments/ltx25-b70/data/na-axis-migration-09/startup-failure.json).
This supersedes every older live PID and next-launch statement below.

**Four-B70 host, September14: decoder packet09 preparation (historical).**
Packet `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-09`
is sealed at manifest`a53e06ae5bd1be8931eff11d4e9112b850912147b37fcabf1bda064b12f419ed`.
The private original-VAEDecode integration passed9 CPU groups; the11-request
client passed14 stdlib checks and offline packet admission. Root reviewed the
node, builder, receipts and client; independent builder review found no blocker.
The new graphs change only decoder374 and retain original transformer dispatch.
Startup must prove the node is registered through object_info before requests.
[Prepared package](experiments/ltx25-b70/notes/na-axis-runtime-09-prepared.md).
PID66846/packet08 is still the live healthy application; no09 native request
or application reload has occurred yet. Next: one controlled application reload
to load09, then the bounded bare/original/cache comparison with full raw parity.

The separate C++ CPU tiny-block probe stopped after detecting unintended XPU
initialization during the first Python-boundary compile; no C++ compiled call
followed. Root checked an empty queue, no FAULT or new kernel entries, and only
the original LTX PID owning the four render devices. That probe stays separate;
its source-backed cache metadata/driver initialization hypothesis and inactive
guarded successor are preserved. Do not run CPU compilation during native timing.

**Two-B70 host, September 14: user-reported freeze during candidate startup.**
The user restarted the computer. Current boot is
`5ba85b30-0455-466a-b9fc-d9132975417e`; the prior boot ended after logs stopped
at about 09:27:55 EDT. The newest-base/V2/DFlash2 candidate never reached
readiness or benchmark requests. Its last model log is target loading, not a
completed draft or generation operation; cause remains unknown. Do not retry
this candidate unchanged. Both GPUs passed bounded compute and XCCL recovery
checks with no new kernel faults. The original R304 FP8/MTP1 service is healthy
at `http://127.0.0.1:18124/v1`, model `qwen38-27b-fp8`; post-reboot strict checks
passed 12/12 complete outputs and all 18 measured
512/2K/16K continuations match the pre-incident control, with cache zero.
Strict decode measured 54.3158 tokens/s and all recovery monitor windows passed.
Its persistent helper owns
`/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/restored-service`.
Preserve the stopped candidate container and all raw evidence under
`/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914`;
`FAULT.json` records the incident. The root fault receipt remains preserved;
the explicit recovery admission
applies only to the original qualified service. The earlier control
and exact-but-neutral projection screen remain valid separate observations.
[Incident receipt](experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer/freeze-incident.json),
[final results and recovery evidence](experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-results.md).

**Four-B70 host, September14: retained profile captured; recorder failed after exact clip.**
The same packet08 PID66846 remains alive and idle, now on **compiled all48**
dispatch. One diagnostic clip matched all four original raw outputs; its graph,
component and owner evidence still passes. The recorder then rejected its own
run name during output inventory (`unregistered/protected run`). No restored
request, retry, deletion, application reload or host action followed. Client
exec11241 exited1; bounded nonblocking profiler exited0. Queue/kernel postflight
clean, no FAULT latch. This is a recorder integration failure, not a device or
numerical fault, and it supersedes the restored-dispatch claim immediately below.

[Profile/postmortem](experiments/ltx25-b70/notes/retained-multiblock-profile-01-results.md)
preserves the trace and exact clip. Offline analysis and a corrected recorder
continue; do not rerun the failed campaign. The saved profile is sufficient for
the next source investigation: decoder geometry-mask construction and native
operation wrapper overhead. No speed promotion or streaming qualification.

The inactive [per-call decoder axis cache](experiments/ltx25-b70/notes/na-axis-cache-01.md)
now passes23 CPU exactness/lifecycle groups, including unchanged SDPA inputs and
call order. Root reviewed the patch and tests. Its source-derived untiled path
reduces522 axis builds to100 with at most1,878 bytes predicted cached payload;
the general cap is256KiB plus allocator/metadata overhead. Native shape coverage,
full-clip equality and speed remain pending. The startup-only scoped router
passed11 actual Kitchen CPU dispatcher lifecycle groups with XPU access
blocked; root reviewed source/tests. [Routing gate](experiments/ltx25-b70/notes/na-axis-router-cpu-01.md).
No installed or loaded runtime source changed. Next: private original-VAEDecode
node integration, complete native shape/route receipts, then a sealed packet and
bounded original/cache/original clip comparison. Keep the C++ experiment separate.

The independent [private C++ operator prototype](experiments/ltx25-b70/native-cpp-ops-01/README.md)
built once on CPU and passed119 operator/fake comparisons with exact outputs.
Small matched CPU dispatch observations are favorable but do not predict XPU
speed; larger RMS samples include a loss and substantial noise. Root reviewed
the C++ source and test/timing drivers. This namespace has CPU implementations
only; compiled tiny-block, XPU and full-clip qualification remain pending.
At16:07UTC the application was still healthy and idle on compiled all48 with
the same boot, empty queue and no kernel/fault evidence after the CPU work.
[Observation](experiments/ltx25-b70/data/retained-profile-final-observation-01.json).

**Four-B70 host, September14: packet08 native screen complete; original selected.**
PID66846 serves `http://127.0.0.1:8188`, manifest
`a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b`.
All12 screen03 clips match all four original raw outputs, including all48
compiled blocks. Compiled previews7.38–8.04s remain slower than adjacent original
controls6.39–6.59s; median penalties1.273s preview/0.927s samplers. No promotion.
Client exec97668 exited0; server exec53546 is idle on restored dispatch with
all48 retained. Queue empty, clean kernel postflight and no FAULT latch.
[Native results](experiments/ltx25-b70/notes/multiblock-screen-03-results.md).
Old PID56711 exited0 after one SIGINT. Same host boot; no computer reboot,
driver reset or power/memory changes. [Startup](experiments/ltx25-b70/data/multiblock-migration-08/startup.json).

Next: complete and review the packet08-only retained diagnostic profiler client,
then one warmed compiled clip with bounded nonblocking stack sampling and one
restored control after all gates pass. This reuses the current application;
no profiler/GPU diagnostic request has occurred yet. It must bind screen03's
same-process qualification and preserve full-output/receipt/identity/fault gates.
The CPU traversal improvement is not a native video speed claim. This supersedes
older live PID56711/packet07 and running-client statements below.

**Four-B70 host, September14: packet07 screen complete; original dispatch selected.**
PID56711 serves `http://127.0.0.1:8188`, manifest
`afdbad186a6873a286f93e9d1e715f6bf4c17e1552d75dbce2a3e03c0a1f35c1`.
All 12 screen02 clips match all four original raw outputs, including all48
compiled blocks. Warm compiled previews7.59–7.65s remain slower than adjacent
restored controls6.37–6.45s (median penalty1.214s preview/1.167s samplers).
Client exec40600 exited0. Server exec70494 is idle on restored dispatch with
all48 retained; queue empty, clean kernel postflight and no FAULT latch.
[Native results](experiments/ltx25-b70/notes/multiblock-screen-02-results.md).
Old PID39793 exited cleanly after one SIGINT. Same computer boot, no host reboot,
driver reset or settings changes. [Startup](experiments/ltx25-b70/data/multiblock-migration-07/startup.json).

A subsequent offline replay measured only52.5ms potential savings from compact
receipt serialization across528 calls, with all parsed fields equal. This is
CPU/filesystem attribution, not a native speed result; no reload is warranted
for it alone. A corrected native-class CPU fixture then measured0.480s per528
route calls with fake compute, preserving1584 state/registry boundaries. The
separate profile points to repeated metadata traversal; this is not native
speed attribution. The inactive single-traversal state/hook candidate then
passed all60 existing lifecycle checks and measured0.313s in the same CPU
fixture versus earlier0.480s. No native speed claim; focused alias/None-state
gates and native qualification remain pending. Next: finish those focused CPU
checks and prepare the next native comparison without touching live packet07.
[Candidate and CPU cost](experiments/ltx25-b70/notes/onepass-state-04-cpu.md).
[Replay evidence](experiments/ltx25-b70/notes/serializer-replay-cpu-01.md),
[metadata attribution](experiments/ltx25-b70/notes/metadata-dispatch-cpu-02-results.md).
This supersedes PID39793/packet06 and running-client statements below.

**Four-B70 host, September14: multiblock screen complete; exact but slower.**
PID39793 serves `http://127.0.0.1:8188` on packet06, manifest
`3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394`.
All 32 clips passed all four original raw-output comparisons, including all48
compiled blocks. Median all48 penalty was +1.303 seconds versus adjacent
restored controls; no speed promotion. The client exited zero. The application
is idle on restored dispatch, queue empty, kernel postflight clean and no FAULT
latch; all three compiled selections remain retained. Server exec38020.
PID17769 exited after one SIGINT; same host boot, no computer reboot, driver
reset or power/memory-setting changes. [Native results](experiments/ltx25-b70/notes/multiblock-screen-01-results.md).

The next inactive adjacent-state reuse03 patch passed all 60 CPU checks for
both parent and candidate, preserving three validation boundaries while
removing two adjacent duplicate state checks per block call. Native quality
and speed remain pending. Prepare its sealed runtime and bounded comparison,
then perform any necessary controlled application reload within authorized work.
[Patch and CPU evidence](experiments/ltx25-b70/notes/adjacent-state-reuse-03-cpu.md).
This supersedes earlier process, inactive-packet and running-client statements below.

**Four-B70 host, September 14: native block compilation exact; paired timing complete.**
PID17769 serves `http://127.0.0.1:8188`, server `encoder-server-compiler-05`,
packet `prepared-encoder-compiler-05`, manifest
`45dc23a7c0a0a234412e31a36225716edf60bb16ad342d96fe12f65139bccbe5`.
All nine compiler-screen-04 clips match all four original raw outputs. Five
compiled clips covered three scenes; both native stages passed eager/compiled
and compiled/repeat checks. Two emitted graphs each retain15 native RMS, six
sigmoid and two tanh-GELU calls. This qualifies block24 only, with no demonstrated
speed win (warm compiled median6.607s; restored boat about6.49s).
Postflight: empty queue, matching identity, clean kernel and no FAULT latch.

The bounded18-request `compiler-timing-01` completed on this same process, with
all original-output checks passing. Median compiled-minus-adjacent-control mean
was+99.797ms preview and+17.977ms sampler intervals: a measured speed loss, not
promotion. The application is idle on restored dispatch, with the qualified
compiled candidate retained and no fault. Across both campaigns27 clips passed,
including11 compiled clips. [Paired results](experiments/ltx25-b70/notes/compiler-timing-01-results.md).

An inactive registry-binding reuse patch removes one duplicate full registry
walk per lifecycle validation while keeping all late-mutation/ownership checks.
Parent and candidate native CPU lifecycle gates passed; no GPU speed result or
deployment. Next: qualify overhead changes and prepare bounded multi-block
selection without per-block application reloads. Continuous real-time generation
remains incomplete. [Patch and CPU evidence](experiments/ltx25-b70/notes/compile-registry-reuse-01-cpu.md).
The multi-block successor now passes CPU qualification. Initial five-block
capture failed at graph9 under the unchanged recompile_limit8; its preserved
successor uses private per-block compiler entry frames and passed10graphs,
20 block cases with exact eager/repeated outputs, plus54 native CPU lifecycle
checks. Packet06 is prepared and inactive, manifest
`3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394`;
its launcher check-only passed. PID17769/packet05 remain unchanged and idle;
passive kernel/fault checks passed. Next: finish the bounded multiblock client,
then a necessary controlled application reload and native GPU qualification.
No new GPU speed/quality result or application reload in this preparation.
[CPU fix and preparation](experiments/ltx25-b70/notes/multiblock-private-entry-02.md).

[Exact native results](experiments/ltx25-b70/notes/compiler-screen-04-results.md),
[scaling/guard audit](experiments/ltx25-b70/notes/compiler-screen-04-conditional-scaling-audit.md),
[prepared source](experiments/ltx25-b70/notes/native-activations-runtime-05-prepared.md).
This supersedes all earlier process and failed-candidate state below.

**Four-B70 host, September14: native RMS compiler successor running.** One
controlled LTX application replacement completed: PID6502 exited cleanly after
one SIGINT; render ownership cleared and the port was available. The computer
was not rebooted. PID12199 now serves `http://127.0.0.1:8188` from
`encoder-server-compiler-04`, packet `prepared-encoder-compiler-04`, manifest
`c4e0f7e56fc7bbc51101894d79d279dd9886f07272868dc99cc7953c647a65c9`.
Four-card startup checks and strict after-import determinism passed; endpoint
identity matched. No fault latch. The candidate preserves original native RMS
calls inside one compiled block; small CPU gates passed, native GPU/full-clip
qualification failed in compiler-screen-03: audio differences fell from5,923 to10
bytes; video remains54 bytes different. Both eager clips matched all original
outputs (warm7.954s). The first compiled block failed before repeat/stage2/full
clip; no speed result is qualified. Queue empty, kernel clean, no FAULT latch.
The numerical gate remains failed; do not retry it. Next is remaining rounding
localization. [Result](experiments/ltx25-b70/notes/compiler-screen-03-results.md).
This supersedes PID6502 and historical blocked/fault states below.
[CPU qualification](experiments/ltx25-b70/notes/native-rms-cpu-qualification-01.md),
[prepared source](experiments/ltx25-b70/notes/native-rms-runtime-04-prepared.md).
The separate native activation successor is now CPU-qualified:21 guard checks,
four tiny block cases, and two emitted graphs each retaining15 RMS/six sigmoid/
two GELU calls. It is not deployed; native GPU and full-clip parity remain
pending. Prepare its immutable packet/client before another necessary controlled
application reload. [Candidate and exact scope](experiments/ltx25-b70/notes/native-activations-cpu-qualification-01.md).

**Two-B70 host, September 14: AMD transfer tests authorized.** The unchanged
FP8 service at localhost:18124 passed 12/12 full-output reference checks and
short/16K continuation controls. A newest-upstream candidate with the accepted
arithmetic overlay is being built for a bounded projection-dispatch and DFlash2
screen. The original service is still running during CPU preparation; one
controlled maintenance transition will precede exclusive GPU testing. No new
runtime or speed result is promoted. Evidence root:
`/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914`.
[Preregistration](experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-prereg.md).

**Four-B70 host recovered after an external boot, September14.** Current boot
`8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a` differs from the faulted boot; all three
old processes are absent. Four-card copy/compute and clean-kernel checks passed,
with render ownership clear after exit. The original FAULT was preserved
byte-for-byte under `external-boot-recovery-01/historical-FAULT.json` and an
explicit recovery admission was recorded there. No reboot, driver reset or host
setting change was performed by this agent. This supersedes the blocked status
below; the full generation goal remains incomplete.

The prepared decoder mask-extent candidate passed all16 small XPU:3 native
mask/attention cases, including BF16/F32 and exact repeats. Kernel postflight is
clean and render devices were released. Full-clip parity and speed are still
unmeasured; installed Comfy Kitchen remains unchanged. Compiler packet03 is now
running as PID6502 at `http://127.0.0.1:8188`, server directory
`encoder-server-compiler-03`, manifest
`9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980`.
Startup four-card checks and strict after-import determinism passed; endpoint
identity matched. Campaign `compiler-screen-02` completed two exact eager clips
(warm control6.262s), then stopped on first native compiled block24 mismatch:
54 differing video bytes and5,923 audio bytes, finite/layout-matched. No compiled
full clip, repeat or speed result is qualified. The queue is empty, PID6502
remains present, the compiler gate is failed, and kernel postflight is clean.
Preserve the process/evidence; do not retry the failed gate. Next is numerical
localization, with native RMS reduction decomposition a source-supported
hypothesis. [Failure and evidence](experiments/ltx25-b70/notes/compiler-screen-02-results.md).
[Recovery evidence](experiments/ltx25-b70/notes/external-boot-recovery-01.md).

**LTX goal blocked on host recovery, September14.** The same kernel fault and
pending-interrupt native clients were revalidated across three consecutive goal
turns. Prepared source work is saved, but the next meaningful steps require a
healthy native runtime: compiler exactness/speed and actual continuation quality.
No new native request, restart or reboot was performed. Generation remains about
6.4s per clip; the full real-time goal is incomplete. Do not continue producing
synthetic-only qualification as a substitute for those native measurements.
[Recovery handoff and resume order](experiments/ltx25-b70/notes/native-progress-recovery-handoff.md).

**Four-B70 host, September14: kernel incident; GPU requests halted.**
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json` is present.
The first compiler-screen-01 eager control clip completed generation, but client
PID96119 became stuck in a kernel cross-CPU TLB wait during post-request work.
CPU13/CPU6 soft lockups, RCU stalls and blocked system tasks are recorded.
Only eager mode ran: no compiled candidate/block execution or completed oracle
qualification. PID95931 remains present with an empty queue; one client SIGINT
was sent, exit unconfirmed. No reboot/reset/restart or host-setting changes were
performed after the fault. The stale campaign `running` status is superseded by
this incident and the fault latch. **No new GPU requests until recovery and
health are established.** Preserve all failed/current clip files and the earlier
25/25 exact encoder results. [Incident and evidence](experiments/ltx25-b70/notes/compiler-screen-01-kernel-incident.md).

Subsequent source progress: the same boot/client kernel wait persists. One
bounded CPU-stack diagnostic timed out without a captured backtrace; no retry,
reboot or new GPU request. Future compiler packet03 is prepared with explicit
host-fault detection; its copied launcher correctly refuses current FAULT.
Runtime remains on packet02, never migrated to03.
[Preparation and fault revalidation](experiments/ltx25-b70/notes/kernel-fault-source-progress-01.md).

Further offline work prepared a continuation graph constructor (13 source tests
passed) and two inactive loader-memory patches. The loader's tiny Torch CPU
test did not finish: PID102144 remains present with SIGINT pending; no numerical
pass or RAM-saving result exists. No further Torch/GPU test retries on this
faulted host. The last durable test artifact is the extracted candidate source,
which does not identify the exact stalled instruction.
[Loader candidate and incomplete test](experiments/ltx25-b70/notes/loader-memory-candidate-02.md);
[continuation source checks](experiments/ltx25-b70/notes/continuation-graph-constructor-cpu.md).

The float-anchor provider and closed continuation graph are now implemented
offline. Thirteen byte-reader tests and12 integration checks passed without
Torch imports; frame extraction also matched independently read final frames
from all three protected originals, whose full-image hashes still matched.
No new video saved or generated. Native tensor construction, runtime deployment,
predecessor lineage, delivery state, continuation quality and speed remain
unqualified. [Implementation and evidence](experiments/ltx25-b70/notes/continuation-anchor-provider-01.md).

Offline continuation work now includes a bounded four-tensor verifier/frame
reader and a single-request coordinator with predecessor binding, explicit sink
acknowledgements, atomic metadata checkpoints and a three-capture admission
limit. Fifteen reader tests and15 simulated coordinator tests pass. Both25/24
frame delivery modes matched independent byte reads for all three original
reference captures, with their four tensor hashes intact. No GPU request,
playback, generation-speed result or footage deletion occurred. Transport,
cleanup, native continuation and playback remain pending; host FAULT persists.
[Bounded state and delivery evidence](experiments/ltx25-b70/notes/continuation-stream-state-01.md).

The inactive continuation verifier now uses exact integer bit intersections
for F32 finite checks. All65 affected bit/reader/provider/state checks pass;
paired scalar/candidate verification of the three original captures produced
identical receipts and all four original hashes. Provisional faulted-host CPU
medians were304.38ms scalar versus44.04ms candidate for full capture verification.
This is verification overhead only, not a generation-speed improvement or
promotion. No GPU request, restart or host-setting change occurred.
[Exact candidate, patch and timing limits](experiments/ltx25-b70/notes/finite-f32-bit-intersections-01.md).

An inactive streaming comparison client now checks complete F32 archive bytes
without importing Torch or loading entire tensors. Fifteen contract tests and
seven arithmetic tests pass. Saved baseline02 and resident-split03 match all
four baseline01 outputs; a different-prompt marble capture correctly fails.
The old comparer and frozen callers remain unchanged. Historical-evidence
reports cannot satisfy a live gate; no generation-speed gain or runtime
qualification is claimed. Host FAULT remains present.
[Candidate and exact evidence](experiments/ltx25-b70/notes/streaming-comparison-01.md).

An inactive one-line decoder candidate removes GPU scalar readbacks when the
attention-window maximum is already available as a Python integer. All17,728
source/integer extent cases pass and the complete AST differs only in that
extent expression. No native mask, attention, full-clip parity or speed result
exists yet. Installed runtime source remains unchanged; FAULT still prevents
native tests. [Patch and qualification scope](experiments/ltx25-b70/notes/na-mask-extent-01.md).
The separate small native mask/attention gate is prepared; its check-only run
correctly halted before importing Torch under the existing fault.
[Gate and refusal evidence](experiments/ltx25-b70/notes/na-mask-extent-native-gate.md).

**Historical startup, superseded by the fault above: native compiler comparison.**
PID95931 serves `http://127.0.0.1:8188` from prepared-encoder-compiler-02,
manifest `f1fc467a4620caabac9065e72fb7fd1628db437d1c977c86237bb0378ef8f952`.
Endpoint identity and strict after-import determinism match the startup receipt.
The bounded nine-request compiler-screen-01 is active; inspect its progress
under `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/compiler-screen-01`
before any new GPU request. It checks one native block24 with the original
control encoder, both native stage outputs against eager/repeat calculations,
and every completed clip against all four original raw references. No compiled
speed or correctness result is claimed before those gates finish.
PID78769 exited cleanly after one controlled SIGINT to load this new application
code; the computer was not rebooted. No fault latch at startup. This supersedes
the idle PID78769 statements below. [Preregistration](experiments/ltx25-b70/data/compiler-screen-01-prereg.json)
and [native gate](experiments/ltx25-b70/notes/ltx-block-compile-node-ready.md).

**Four-B70 host, September14: encoder comparison complete; compiler integration next.**
All25 encoder-screen-02 clips passed strict four-output original-reference parity
and all four unload transitions passed. No convincing speed winner: warm medians
6.364s control-before,6.377s crop,6.430s small-state,6.441s combined,6.643s
control-after. Small-state residency fixes the observed loaded-byte accounting
drift, but has no demonstrated full-clip speed gain. PID78769 is idle on control,
generation5, at `http://127.0.0.1:8188`; no fault latch. Preserve this process
while preparing the compiler successor; no competing GPU requests. Next is a
bounded one-native-block exact compilation gate, then full-clip verification if
it passes. [Results](experiments/ltx25-b70/notes/encoder-screen-02-results.md).
This supersedes the active-screen statements immediately below.

**Four-B70 host, September14: strict startup fixed; encoder comparison started.**
PID78769 serves `http://127.0.0.1:8188` from prepared-encoder-03 / encoder-server-02.
Startup identity matches the endpoint and the after-import receipt verifies
strict determinism (enabled, warning-only off). Encoder-screen-02 is running;
reuse this process and inspect its progress before any new GPU request.
The first screen on PID75850 stopped after one completed control clip: all four
outputs matched baseline bytes, but strict-mode qualification failed because
Comfy import reset warning-only mode. The corrected launcher restores the
original import order;11 CPU regression checks passed. Only the launcher differs
between the immutable packets. No quality gate was waived. Evidence and exact
scope: [startup correction](experiments/ltx25-b70/notes/encoder-strict-startup-fix.md).
User clarified that routine application reloads should not cause approval
pauses or stop optimization; the host-reboot/power/restart-chain constraints
remain. This supersedes all earlier pending-approval and process statements below.

**Four-B70 host, September14: authorized LTX replacement completed.**
User approved the restart and clarified that optimization must continue without
an unnecessary application-restart approval pause. Original PID24848
stopped cleanly after one SIGINT. Replacement PID75850 is ready at
`http://127.0.0.1:8188`; endpoint identity matches the encoder-server-01 receipt,
the queue is empty and the fault latch is absent. Host LAN IP is10.0.0.65, but
the application listens on localhost only. The immutable prepared-encoder-02
packet is active. The preregistered encoder-screen-01 comparison is now running
on this process; inspect its live progress before any new GPU work. An initial launcher
preflight exited before Torch import because the old TCP socket was in TIME-WAIT;
after its observed expiry, the bind check passed and the replacement started.
Evidence: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-migration-01.json`
and `encoder-server-01/`. This supersedes pending-replacement statements below.

**Four-B70 host, compiler preparation: routed CPU gates pass; inactive.**
The native block adapter passed its initial 29 checks; the additive ownership
guard passed 51 checks with the compiler callback itself in the full options
registry. Both stage token counts and two seeds matched video/audio outputs
exactly and repeated identically, with two compiled graphs and no graph breaks.
These are tiny CPU fixtures, not native-weight GPU or speed results. The
[checkpoint header census](experiments/ltx25-b70/notes/native-block-header-census.md)
records native block dimensions and mixed stored dtypes without loading weights.
A subsequent [executing-patcher lifecycle gate](experiments/ltx25-b70/notes/ltx-block-compile-pre-run-lifecycle.md)
passed 25 CPU checks for live owner anchoring, late changes, clone behavior and
cleanup. A subsequent [real bound CPU capture](experiments/ltx25-b70/notes/ltx-bound-lifecycle-capture-cpu.md)
passed one 64-video/26-audio-token case with the lifecycle callback present:
both outputs exact and repeatable, one compiled graph and zero graph breaks.
Native GPU correctness/overhead and broader cases remain unqualified. The
cancelled optional CPU compilation attempt is preserved separately. The
[continuation audit](experiments/ltx25-b70/notes/continuation-source-boundary.md)
also records two-stage mask loss and unresolved audio timing before streaming.
PID24848 remains idle, fault-free and unchanged; the encoder v2 maintenance
approval is still pending after multiple goal turns. The prepared launcher again
passed its read-only check. Further measured speed work is waiting on that
decision; do not infer approval from automatic continuation. Compiler work is
separate from that immutable packet.
See the [route gate](experiments/ltx25-b70/notes/ltx-block-compile-route-cpu.md).

**Four-B70 host, encoder runtime v2: GPU screen prepared, maintenance pending.**
Startup, actual placement/unload diagnostics and the 25-request bounded client
are complete. Eight startup, ten diagnostics and eight client CPU tests pass;
the copied launcher's read-only check passed and all 1,214 packet files still
match their hashes. No new GPU request, runtime change or server replacement
occurred. PID24848 remains running and idle, with its original identity and no
fault latch. The new `encoder-server-01` directory does not exist. One deliberate
graceful replacement is needed to load v2; do not start a second process beside
the current server or create a retry/restart chain. The next action is a
maintenance decision for the [concrete launch and screen](experiments/ltx25-b70/notes/encoder-runtime-v2-ready.md).
The source snapshot is `prepared-encoder-02`, manifest SHA256
`920d0e35774f298c9b11f80b3dd5e3708d0541f914e4c1857e96493bfd7282a8`.

**Four-B70 host, encoder integration follow-up: inactive source packet built.**
The four encoder variants now pass 17 CPU lifecycle tests and four integration
tests through tiny real Gemma4/CLIP/LTX projection paths. Review fixed a shared
clone policy bypass; integration also fixed rejection of CLIP's stock compute
dtype setting. Original patches and earlier receipts remain preserved. A new
non-Git source snapshot under `prepared-encoder-01` inventories 1,205 files and
keeps all baseline graph inputs except explicit encoder options. Every staged
file hash and the unchanged loaded-source hashes passed verification. No GPU
job, server restart or runtime edit occurred. PID24848 remains the loaded idle
service; no new speed claim. Next: finish startup identity/client and actual
placement diagnostics before any maintenance decision or the bounded 25-request
comparison. See the [source packet and remaining gates](experiments/ltx25-b70/notes/encoder-runtime-packet.md).

**2026-09-14 UTC, two-B70 host: bounded worker comparison finished; FP8 ready.**
Readable tool output passed stable acceptance and independent agent review on all
five original issues, plus one confirmation each of the formerly failed hardware
and zero-cost tasks. Both new held-out issues failed. The readable profile remains
opt-in/experimental; original defaults and model performance qualification stay
unchanged. All generated patches remain unmerged, with human review pending.
[Results and evidence](experiments/local-coding-worker/overnight-2026-09-14-results.md).
The original 3/5 trial and first failed profile screen remain frozen separately.

One unchanged qualified FP8 TP2/MTP1 server remains healthy at `127.0.0.1:18124`,
33,024 total capacity / 4,096 scheduling batch / one active sequence. Exact helper
state/logs: `/mnt/fast-ai/bench-results/local-worker-20260914/server/`.
All nine corrected-campaign CPU containers stopped before patch export. No model
patch was applied to either source checkout. No server restart, inference
optimization, host-setting change, local GPU fault or cloud fallback occurred.
The eight-hour authorization was an upper bound; this bounded model campaign is
closed. No queued model/GPU tasks remain in this lane.
Use the existing endpoint for subsequent worker jobs; do not launch a competing
GPU lane. [Worker commands and API capacity](worker/README.md).
Preserve independent four-card LTX work and its fault-halt state above.

**Four-B70 host, post-stability LTX diagnostics: next runtime candidates prepared.**
One 15-second nonblocking py-spy attachment and one unchanged clip completed on
PID24848; all four output tensors matched baseline-01. The trace points to
repeated CPU copies of tiny encoder RMSNorm weights and layer scalars totaling
only 1.47 MiB. The opt-in small-state residency patch passed 12 real Gemma4 CPU
lifecycle tests; it includes a scoped accounting correction and must not be
stacked with the separate generic accounting patch. It is inactive.
Stock whole-model compilation was rejected by source audit. Default CPU
Inductor changed BF16 values despite deterministic repeats; preserving rounding
passed 6/6 toy cases. An actual native LTXAV block CPU fixture then passed both
stage token counts: two compiled graphs, zero graph breaks, both outputs exact.
These are CPU preparation gates, not GPU speed/quality results. No server restart
or runtime patch occurred; the server is idle and fault-free. Diagnostic media
was pruned after exact verification. Next work is a bounded runtime integration
packet for small-state residency/cropping and one-block compilation; do not use
the unsafe stock compile node or inject code into the live process.
See [profile result](experiments/ltx25-b70/notes/stack-profile-01-results.md),
[small-state candidate](experiments/ltx25-b70/notes/encoder-small-state-audit.md),
and [compiler block gate](experiments/ltx25-b70/notes/ltx-block-compile-cpu.md).

**2026-09-14 UTC, two-B70 host: official FP8 quickstart replay complete.**
The public-source helper ran one R304 TP2/MTP1 server at 33,024 capacity /
4,096 batch / one sequence. Strict 12/12 complete outputs matched the qualified
reference; all six practical requests passed with exact repeated outputs and
zero cached tokens. Single-replay decode 54.201 tok/s; no optimization promoted.
The documented exact-owned stop passed, all owned processes/listeners are gone,
and both GPUs/XCCL plus the full journal postflight passed. State and logs are
under `/mnt/fast-ai/bench-results/qwen-fp8-flagship-20260914`; the hash-bound
[results packet](experiments/qwen38-27b-b70/notes/2026-09-14-fp8-flagship-results.md)
records public commit, image/model checks and remaining installation limits.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, September13, LTX campaign started toward the revised goal.**
User requires one second of new video in **under one second**, at24fps with no
quality/losslessness sacrifice. Final output floor is256x256; <=3s is only an
intermediate marker. Minimal rolling review footage is authorized, including
deleting older verified campaign outputs while preserving compact hashes and
receipts. Existing model/reference artifacts stay protected. The first bounded
work completed [30 sequential requests over10 fixtures](experiments/ltx25-b70/notes/stability-01-results.md)
on the existing PID24848 endpoint: all exact repeats passed, median preview6.515s,
p956.680s, no faults/OOM. Physical memory stayed within observed bounds while
the encoder's reported offload grew690→2718MiB; source/CPU work supports an
accounting defect. Longer soaks remain deferred. Verified pruning reclaimed607MB,
retaining three campaign previews totaling170KB plus compact receipts. Two
inactive candidate patches target accounting and unnecessary hidden-state CPU
copies; no runtime change or further restart occurred. The server is idle.
See the updated [plan](experiments/ltx25-b70/PLAN.md).


**2026-09-13 EDT, two-B70 host: final FP8 prefill pass complete and stopped.**
Official 27B FP8, R304 TP2/MTP1, measured 512/2048 inputs at 2,857/3,679 input
tokens/s with 4096 capacity/batch. All 36 measured outputs repeated exactly;
strict 12/12 original-reference parity, decode −0.13%. Profiling found FP8 matrix
operations dominant and no justified quick candidate; defaults retained and
prefill campaign closed. Owned server stopped, both GPUs/XCCL and journal
postflights passed. [Results](experiments/qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md).
Raw root `/mnt/fast-ai/bench-results/qwen-fp8-prefill-focus-20260914`.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, 2026-09-13 22:23 EDT: exact-output LTX speed result.**
User prioritizes first usable clip within a few seconds, while retaining exact
baseline outputs. Baseline PID11499 exited cleanly after one planned SIGINT;
new ComfyUI PID24848 owns `127.0.0.1:8188`, with the same exclusive locks,
strict deterministic mode and cache-none computation. All four small startup
preflights passed, with no device fault. Resident model components and exact
layer placement are startup extensions; generated outputs and prompt encodings
are always recomputed. **Validated warm 256x256/25-frame clips take 6.44–7.10 s
to playable preview**, using all four B70s: transformer split across XPU0/1,
encoder XPU2 and VAEs XPU3. Three boat repeats and marble/bird reference scenes
match all four original tensors bitwise. Exact float media export also passed.
Matched warm boat client medians improved 7.85×; first split initialization took
81.21 s to preview. BasicGuider was exact but neutral and is not selected.
The one-second clip is not yet continuous real time; prolonged operation remains
untested. The transformer stays resident; the encoder still partially offloads.
Server is idle with split components retained. Further variants
use this same process; no restart chains/power/swap/cache-drop/driver changes.
See [speed campaign handoff](experiments/ltx25-b70/SPEED-HANDOFF.md).
The [LTX north star and plan](experiments/ltx25-b70/PLAN.md) now define the next
milestones: bounded stability validation, exact clips under1s, coherent streaming,
then sustained generation above24fps. The later start instruction is recorded above.
Original baseline remains frozen; new process identity is under the original
evidence root's `speed-server/`. Use `profile-clip.py --server-run` pointing there.

**2026-09-13 21:47 EDT, two-B70 host: bounded prefill follow-up complete.**
4B TP2, 9B TP2 and 27B INT4 TP1 measured at 256/512 input tokens, one user,
cache zero; all 108 measured requests repeat exactly and all three strict suites
match their original qualified outputs 12/12. One 4B TP2 profiler trace is
retained; no new runtime candidate or decode record promoted. All three owned
servers are stopped, both GPUs/XCCL and journal postflights passed. [Results](experiments/qwen38-27b-b70/notes/2026-09-14-prefill-followup-results.md),
raw evidence `/mnt/fast-ai/bench-results/qwen-prefill-followup-20260914`.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, 2026-09-13 20:42 EDT: LTX baseline bring-up.** User authorized
a very short native-precision clip and deterministic repeat checks. One local
ComfyUI server (historical PID 11499, `127.0.0.1:8188`) ran with exclusive device
locks; all four cards passed its small copy/compute preflight. **Baseline complete,
original server since replaced as described above:** three fixed-seed 256x256/25-frame generations are bitwise identical
across images, video/audio latents and waveform, with strict determinism and zero
cached nodes. First/repeat server times were 97.590/54.009/52.774 seconds. Exact
float video/audio export passed independent decode round-trip verification.
No GPU fault, OOM or tiled-VAE fallback occurred. This establishes one-prompt,
same-process repeatability, not cross-process or other-model parity. The RAID transformer and encoder failed fresh
SHA-256 checks; rejected bytes and failed receipts are preserved. The transformer
was repaired by replacing 79 damaged bytes, and the encoder by replacing 112.
All five final component files passed publisher/direct-I/O hashes; the generation
gate is now open. Rejected files and partial downloads remain preserved. Preserve the server, source and environment at
`/home/steve/src/ComfyUI-ltx25-baseline` and
`/home/steve/.venvs/ltx25-baseline`; no restart chain or power-setting changes.
See [verified baseline and reuse instructions](experiments/ltx25-b70/README.md). Evidence root:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

**Four-B70 host, 2026-09-13 after 20:17 EDT reboot: LTX 2.5 pivot.** User
requested parking the completed Flash-Next campaign, archiving its checkpoint
to USB, then focusing on LTX 2.5. Recent LTX, YuE2 and MiniCPM downloads were
located on the RAID, now mounted read-only. Corsair's read-only mount failed
with an NTFS chkdsk recommendation; Qwen archive verification/reclaim is
pending, and the internal checkpoint remains intact. No GPU workload was
launched. The active task is storage/download review and LTX bring-up planning;
prior queued four-card launch instructions are superseded. See the
[pivot and storage review](notes/2026-09-13-ltx25-focus-and-storage-review.md).

**2026-09-13 20:30 EDT, two-B70 host: short-prefill campaign complete.**
Measured 4B/9B W4A16 and 27B INT4/FP8 at c1 with 128/256/512-token inputs.
All 324 measured requests were cache-zero and output-exact across off/on/off;
each model passed 12/12 full-suite candidate/control and original-reference
parity. A direct-output allocation screen showed +3.0% on 4B, +2.1% on 9B,
and neutral 27B results, with strict decode differences below 0.3%. Existing
serving defaults remain unchanged; this is a single-process screen, not a new
promotion. See the [results and replay](experiments/qwen38-27b-b70/notes/2026-09-13-short-prefill-results.md)
and [complete summary](experiments/qwen38-27b-b70/data/2026-09-13-short-prefill/summary.json).
All four model stages are stopped, optimization flags removed, both GPUs/XCCL
and final journal postflights passed. No power, swap, cache-drop, driver or
reboot changes. Raw evidence remains at
`/mnt/fast-ai/bench-results/qwen-short-prefill-20260913`.

**2026-09-13 19:32 EDT, two-B70 host: R308 work complete.** The optional
single-request repair for Qwen3.5 4B and 9B is published, anonymously pullable,
and verified on the live site. Both models passed 60/60 oracle checks,
52/52 boundary checks on each of two fresh speculative servers, and all four
strict comparisons 12/12. Public-parent reconstruction matched all 17 runtime
hashes. Source/evidence integrity, guide tests, recipe CI and Pages deployment
passed. See the [qualification note](experiments/qwen35-4b-b70/notes/2026-09-13-r308-qualified-single-request.md)
and [completion receipt](experiments/qwen35-4b-b70/data/2026-09-13-r308-single-request-qualification/evidence/publication/completion.json).
All owned model and preview servers are stopped; both GPUs and XCCL passed
final health checks. No power, swap, driver, or reboot changes were made.
Scope is TP1, fixed depth 3, one active request: boundary capacity 256 and strict
capacity 1024. Clean-host certification, concurrent speculation and a new 32K
profile remain outside this qualification. R307 failures and diagnostic roots
remain preserved in the linked evidence; existing defaults retain their
original identities.

**Four-B70 Flash-Next closeout, 2026-09-13:** user requested finishing Fable's
optimization campaign and publishing existing results. A340-A394 is closed:
46.854250 tok/s approved realistic-suite record, +23.87% vs previous line;
A382/A394 repeated 32K depth median 44.052 tok/s with equal output hashes.
[Closeout](results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md) owns the wins,
nonpromoted trials and remaining certification limits. No server or optimization
chain is running. The separate disabled single-session draft is set aside.
User constraints remain: no AI power-setting changes and no repeated restarts.

**Four-B70 host, 2026-09-13 20:10 UTC recovery:** A394 depth repeats pass, but
teardown rc is 143 and another host interruption followed. No workload running;
hold Flash-Next launches pending teardown/host-restoration review. Git damage
restored from the already-pushed A394 commit; evidence USB mounted read-only,
RAID unmounted. See [recovery evidence](notes/2026-09-13-a394-freeze-recovery.md).
Follow-up: full Git fsck passes, NVMe reports zero media/errors; offline audit
found stop-protocol mismatch, stale health receipts and a nested-cleanup race.
See [teardown audit and next gates](notes/2026-09-13-a394-teardown-audit.md).

**2026-09-13 (EDT):** the whole INT4/W4A16 runtime is rebased onto stock vLLM XPU
v0.29.0 as **R304** (`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16`,
pushed and anonymously pullable): the R294b overlays ported as net diffs, the kernel
library rebuilt from public sources (vllm-xpu-kernels 0.1.14.1, which carries upstream
GDN fix #544, plus the lab's oneDNN r137a/r137b/r221), and three open upstream vLLM
fixes applied verbatim (#53059 alias guard, #51565 GDN first-chunk, #53542 active width).
It fixes two failures that were live on R294b: every one-token prompt and every
(1+K)-token prompt at depth K degenerated into single-character walls (30/30). Strict
gates 12/12 at published speed on the 4B, 9B and FP8-27B lanes under the recipe contract
(`verify-image-contract.sh` v0290 digest set); the INT4-27B pair is running. The 4B and
9B and both 27B recipes, packages and compose packets now point at R304 (all gates 12/12, long context 18/18,
high concurrency reproduced; kernel library reproduced bit-identically from a clean clone). The 9B scheduled-draft
profile runs on R306 (`@sha256:f124c6fb`, R304 plus its overlays and a contiguous-staging fix for upstream PR #53542). Serve with `VLLM_USE_V2_MODEL_RUNNER=0` (the launchers pin it; v0.29.0
defaults XPU to the V2 runner, which has no draft INT4 head). Details:
`experiments/qwen38-27b-b70/notes/2026-09-12-rebase-onto-vllm-v0290.md`.

**2026-09-11 (EDT):** the Qwen3.5 4B/9B and Qwen3.8 27B INT4 lanes finished the
class-consistent FP16 linear work (R290-R293 overlays, `VLLM_XPU_FP16_LINEAR_CLASSPAD`):
the R224 32-row pieces re-read the vocabulary projection once per 32 rows, 25-56% of
throughput on the 4B/9B and 3-8% on the 27B, removed losslessly. 27B package staged
on R293 (`packages/qwen38-27b-int4-fixed-k-tp2-b70`, rows R295-R298); the R293
image is built locally (`sha256:40d46730`) and awaits the GHCR push
(`repro/qwen38-27b-autoround-int4-b70/scripts/publish-r293-image-ghcr.sh`). No
containers running after 19:03 EDT; both cards passed postflight.

Host: `steve-TURIND8-2L2T`, **two B70s**. At the verification time above,
no Docker containers are running; all PR45 review servers were stopped.
Both GPUs and XCCL passed final postflight. Recheck actual process and endpoint
state before operational changes.

Target-oracle follow-up completed: both fresh compiled target-only strict tests
passed, all five comparisons were 12/12 exact, and 96 additional probes passed.
All owned containers stopped; localhost 18124 is closed and postflight passed. See
[preregistration](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/target-oracle-20260909.md).
The six-hour soak has not been started.

The active task is correctness and reproducibility review. An isolated
Qwen3.8 27B official-FP8 R50 baseline/candidate comparison completed for PR #45:
normal-suite parity passed, tiny-prompt screens failed, candidate not promoted.
The initial review model containers were stopped; both GPUs and XCCL passed
postflight. Follow-up isolated the fresh one-token GDN routing defect: the
phase-guard candidate passed 120/120 probes, two fresh compiled MTP full suites,
12/12 baseline/fresh-repeat parity and pre/post workload screens. The campaign
is complete and stopped, not a permanent service. See the
[preregistered follow-up](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-followup-plan.md).
Read the
[maintainer validation record](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/README.md)
for the candidate identity, completed tests and outstanding gates.

The previous Gemma listener and Qwen3.5 active-lane claims are superseded by
this observation. Preserve the existing Qwen3.5 work listed below. Run one
GPU lane at a time; verify endpoint and health independently of an image tag.

## Working Recipes And Candidates

- **Qwen3.8 27B FP8 TP2:** the [reproduction packet](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md)
  owns the lab-qualified R187 configuration, exact-output concurrency limits
  and historical results. Its certification remains `candidate-portable-repro`;
  it is not a verified beginner setup. Consult the
  [multi-host handoff](experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md) and
  [do-not-repeat index](experiments/qwen38-27b-b70/DO-NOT-REPEAT.md) before work.
- **PR #45 classifier fix:** separate R50 candidate, not promoted into the
  above recipe. Actual-source CPU checks pass against both source copies.
  Normal GPU suite passed 12/12 exact baseline/candidate parity, but both
  failed tiny-prefill screens; compilation-disabled candidate also failed.
  Sustained mixed-session validation remains unperformed; not a verified fix.
  A separate maintainer GDN phase guard fixes the local one-token symptom in
  the [bounded follow-up](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-20260909/README.md),
  but is not promoted as the contributor's incident resolution.
- **Gemma 4 26B Q8:** [result/handoff](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
  and [standalone recipe](repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
  preserve the measured setup. Their existence does not mean Gemma is loaded.
- Other lane status belongs in the [model effort index](docs/model-effort-index.md)
  and [reproducibility map](docs/current-reproducibility-map.md).
  The [scoreboard](results/scoreboard.md) is historical measurement evidence,
  not service state.

## Known Issues And Next Actions

1. Before promoting the GDN local fix, run the contributor's actual mixed-session
   soak. The matched-image MTP0/MTP1 strict-oracle matrix now passes; the
   multi-hour incident remains unverified. PR #45 is merged as a community
   contribution, not a production promotion.
2. Reproduce one selected recipe end to end: pinned inputs, build, launch,
   quality gate and clean teardown. Correct defects found along that route
   before additional speed tuning.
3. Audit recent changes by affected runtime, shared harness and published
   recipe. The [September 8 review](notes/2026-09-08-targeted-correctness-cleanup.md)
   was bounded: syntax checks are not execution coverage, and commit author
   labels do not establish which model wrote a change.
4. Three promoted Flash-Next replay paths now use exact frozen verifier
   snapshots; four replay clients now stop their servers on failure. Bundle
   chains were restored and verified from the public base. See the
   [audit record](notes/2026-09-09-replay-and-validator-audit.md).
   The broader 229 historical experimental hash mismatches were not blindly
   repinned. Four-card runtime replay remains untested on this two-card host.
5. Keep ML Bottleneck automatic refresh paused. Numerical fixture tests are
   now separated from refreshed-data checks. The ingestion parser correction
   passes 94 tests and resolves the 3060 interpretation in a migration test.
   Publication still blocks on the 4070, nine ambiguous measurements and
   calibration thresholds. Published evidence remains unchanged. Details are in
   that repository's `docs/refresh-review-2026-09-08.md`.

## Other Host: Four-Card Work

MiniMax M2.7 INT4 and Flash-Next TP4 belong to the **four-B70 host**, not
this two-card machine. The [MiniMax post-reboot note](notes/NEXT-minimax-after-reboot.md)
is that host's resume packet; its remount, driver and launch instructions
must not be applied here. It records an unresolved bring-up validation after
a driver wedge, not a successful serving result. On the owning host, avoid
polling `xpu-smi` during initialization, verify the four devices and use its
bounded health checks before continuing.

Flash-Next history and accepted identities live in its
[handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md) and
[result packet](results/qwen38-flash-next-fp8-b70/README.md).
Historical reboot notices in the archive do not describe this boot.

### Four-B70 host, 2026-09-11: Qwen3.5-9B W4A16 lane closed, Flash-Next next

The Qwen3.5-9B W4A16 one-B70 lane on `steve-b70s` is closed and published: the
static depth-3 headline (113.27 tok/s) stands, and a second operating
configuration - one server for every batch size, draft depth scheduled by
batch size on three pure-Python overlays over R276 - is promoted in the
[guide](repro/qwen35-9b-w4a16-b70/README.md#one-server-for-every-batch-size-campaigns-cudynm1--cudynm1r-2026-09-11),
[package](packages/qwen35-9b-w4a16-b70/package.json) and
[performance index](results/scoreboard.md): 110.7 tok/s at one user, 1,184 at
64 users, exact through 32 users, 18/18 exact 2K-32K. The env-knob ladder for
single-user decode on this lane is exhausted (defaults optimal on every axis);
what remains is kernel work (fused INT4 draft head) recorded in the
[campaign note](experiments/qwen35-9b-b70/notes/2026-09-10-one-server-for-every-batch-size.md).
No lane container is running. The next active lane on this host is Qwen3.8
Flash-Next (its [handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md)).

### Four-B70 host, 2026-09-13: Flash-Next lossless MTP1 at 46.85 tok/s (record approved)

The Flash-Next lane's step-timing decomposition (A340-A358) put 8.7 ms of the 42.7 ms
two-row verify step in vLLM's Python serial GDN path and showed the cost is in neither its
kernels nor its glue. The kernel extension's own exact serial mode, gated to four verifier rows
by the served build, accepts two when `_xpu_C.abi3.so` is rebuilt from the lane's kernel head
(`bbae3c5` over `e421889`, [series](patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/README.md)).
With that mode selected the verify step is 33.7 ms and every output pin holds (kernel probe
bit-identical; exact-2K `afffd211…`, exact-4K `1d833e5f…` on four servers; 12/12 suite outputs
equal to the 37.83 record). Certified on three servers (A364, A365, A366: short 53.4, exact-2K
48.2, exact-4K 48.5 tok/s) and recorded on a fourth (A367: **46.854250 tok/s** class-balanced,
LocalMaxxing [`cmtzask41000nlq011f16bpbc`](https://www.localmaxxing.com/runs/cmtzask41000nlq011f16bpbc)
approved). Guide [`repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/`](repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md),
package `packages/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/`, narrative in the
[result packet](results/qwen38-flash-next-fp8-b70/README.md). Host notes: two silent freezes hit
launches started 60-90 s after the previous server's teardown (swap toggle); leave five minutes
between a stop and the next launch. Unused models (laguna-s-2.1, muse-glimmer, the 9B pair) were
moved to `/mnt/raid-models` with symlinks left in place; root NVMe at 301 GB free. No lane
server is running.

## Protected Work And Artifacts

Preserve these paths and inspect their status before any build, cleanup, or
service change:

- `/home/steve/src/llama.cpp-muse-100`: preserved source/build used by the inactive Muse fleet;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2`: accepted Qwen3.8 Q4_K_M source at
  `a4349bcee`; preserve its intentional three-file uncommitted fusion delta;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2/build-sycl-aot-bmg-g31-oneapi-2026.1.1`:
  accepted oneAPI 2026.1.1 BMG-G31 AOT build;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gguf/`: accepted Qwen3.8 GGUF targets and MTP sidecars;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/`: official FP8 artifact retained for the separate vLLM lane;
- `/mnt/fast-ai/bench-results/qwen38-official-fp8-vllm-xpu-20260816/`:
  official FP8 eager/graph/P2P controls, final quality gate, cache-zero result,
  runtime capture, and post-run health evidence;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp/`: hash-verified
  SergioB GPTQ INT4 target with 15 BF16 MTP tensors; community replay lane;
- `/mnt/fast-ai/bench-results/qwen38-q4km-asrock-b70-20260815-pass2/`:
  accepted Q4_K fusion A/B and cold-suite evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`:
  SergioB target-only eager/graph validation, failed conservative-U graph
  attempt, logs, inspect records, prompts, and raw SSE evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-quality-20260816/`: native/FP8 KV,
  semantic quality, MTP runtime-dtype, Q8/Q4 controls, and reset-window evidence;
- `/mnt/fast-ai/src/llama.cpp-q8-tp2-directq8-isolated`: current accepted Qwen TP2 source;
- `/mnt/fast-ai/src/llama.cpp-q38-tp2-distributed-greedy-directq8`: closed
  exact distributed-argmax candidate; preserve for mechanism reuse only;
- `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-distributed-greedy/`:
  position-balanced reasoning-off controls/candidates and exact output oracle;
- `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`: prior accepted Qwen TP2 source; preserve as control;
- `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/`: accepted Qwen model;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion/`:
  promoted Qwen evidence and bounded negatives;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260814-40tps/`:
  Qwen pass-1/pass-2 evidence and current clean result;
- `experiments/qwen27_graphsafe_flash_attention/`: graph-safe INT4 source and
  generated research state;
- `experiments/qwen36-27b-autoround-int4-b70/`: INT4/MTP research packet and
  diagnostic artifacts.

Large ignored Qwen artifacts may be archived only after a complete inventory,
hash verification, and a recorded restore path. Never use broad `git clean` or
delete tracked experiment material to make the tree look tidy.

## Additional Preserved Work And Operational Guards

Pre-existing dirty Qwen3.5 work at review start; inspect and preserve:

- `experiments/qwen35-9b-b70/probes/drift-reproduction.py`
- `experiments/qwen35-9b-b70/scripts/analyze-admission-composition.py`
- `experiments/qwen35-9b-b70/scripts/run-20260908-drift-reproduction.sh`

The prior ledger also protects the dirty Flash-Next source tree; do not
reuse or modify it for the Qwen3.8 R50 review. Root-NVMe/BIOS work remains
paused. Retain the existing frozen-runner guards: no bulk reads/scans of
`/mnt/fast-ai` or `/mnt/usb-models`; do not start
`generate-q38-root-nvme-link-clearance-v1.py` or any `w13`/`hc` runner.
Do not run process-search commands containing
`w13-m1-xpu-graph-gate.py` or the A2 result path: frozen health checks can
mistake the search itself for a surviving runner. See the
[archived ownership notice](CURRENT-history-20260909.md#immediate-manager-actions)
for the original guard and its recorded false positives.

Do not place new model downloads on NVMe based on an old free-space report.
Verify current capacity, mount identity and lane ownership first. Follow
[AGENTS.md](AGENTS.md) for main-only Git, secrets, runtime isolation,
quality gates and exact publication requirements.
