# Flash-Next official FP8 return survey — 2026-10-16

**Return to the certified four-B70 FP8 identity, establish a safe load and exit,
then measure the remaining M=2 glue before choosing a speed patch.** The record
is still **46.854250 tok/s**. The old 8.8 ms GDN excess was largely removed to
make that record; it is not another unclaimed win. The October repairs establish
one clean experimental startup, not a certified-runtime generation replay.

This is a read-only survey of repository evidence on `steve-b70s`, with only
this note written. Analysis commands used cores 4–15,20–31, nice 19, ionice
class 3 and `python3 -B` where applicable. No builds, device access, XPU-SMI,
sudo, services, endpoints, model payload reads or protected source/archive
inspection. Initial main was fast-forwarded to `e60763dfd5144ffe27f90c979bb9eb0eea35dce7`.
Existing untracked experiment receipts were preserved. [CURRENT.md](../CURRENT.md)
is recorded state, not a fresh idle-card or health attestation.

## 1. Record identity and reproduction boundary

The [September closeout](../results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md),
[current handoff](../results/qwen38-flash-next-fp8-b70/HANDOFF.md),
[replay guide](../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md)
and [full identity](../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/identity.json)
bind the following:

| Item | Exact record |
| --- | --- |
| Run | A367, September 13; LocalMaxxing `cmtzask41000nlq011f16bpbc`; stored rate `46.85424994838007` tok/s |
| Metric | One user; fixed 12-prompt realistic cold suite; median of class medians; 99 inter-token intervals between events 1 and 100 after TTFT |
| Target | Official `Qwen/Qwen3.8-Flash-Next-FP8`, revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`; 131 shards, 185,563,783,127 root bytes |
| Runtime source | Public vLLM base `76cfe1cd88d30d525eec8be5bff75f8b77471c88`; overlay `6d8724577dabbee5fa0bbc70c4d927c6174c8d8a`, tree `3e8dfc5937087d186cd4a99a6bf15213be732462` |
| Overlay chain | Lossless MTP1 `1b2a17c1` → placement `005dc578` → Triton HC `62219122` → fused QSA `6d872457`; the guide links every retained patch series |
| Native kernels | Hybrid stage v2: served `2f829747` stage with `_xpu_C.abi3.so` rebuilt from `bbae3c59e226c1b0c2a2dca6c51b4465cf36fd26` over `e421889999bc1e5a5f11044d14548b9afdba644d`; 18 loadable files in the [stage manifest](../experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-gdn-roundstate-v2-loadable.sha256) |
| Host environment | Python 3.12, Torch 2.11.0+xpu, Triton 3.7.0, oneAPI 2025.3; oneCCL `4ceafd1`, libraries pinned in identity.json |
| Image | **No certified record-compatible container image digest exists.** A367 used the native host venv and staged libraries. The copied container recipe has an incompatible Torch ABI and is not an alternative replay |
| Topology | Four B70 32 GiB, TP4 + EP4, `ZE_AFFINITY_MASK=0,1,2,3`; Triton MoE; `allgather_reducescatter` |
| Capacity and cache | Length 4,352; one sequence; 64 batched tokens; full 16-bit BF16 KV, 376,569,856 bytes/rank, BLHNC |
| Graph | Compilation mode NONE; `FULL_DECODE_ONLY`; capture sizes [1,2], maximum 2, one warmup |
| Placement | UVA offload 12.25 GiB/rank for PLE and input embeddings; [certified expert map](../experiments/qwen38-flash-next-fp8-b70/data/20260906-q38-expert-host-placement-3p5gib-per-rank.json), SHA256 `f3f4812cfae2f4f704e75cc9b47a4031a476f846b353e3def23141b9d9c05f96` |
| Speculation | Publisher MTP, `num_speculative_tokens=1`; target verifies every accepted token; no prefix reuse or async scheduling |

The effective selectors are:

```text
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_MKLDNN_DETERMINISTIC=1
VLLM_XPU_HC_TRITON=1
VLLM_XPU_QSA_FUSED_INDEXER=1
VLLM_XPU_GDN_SERIAL_SPEC_DECODE=0
VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1
VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER=1
VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2
VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2
CCL_SYCL_ALLREDUCE_LL=twoshots
CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096
VLLM_TUNED_CONFIG_FOLDER=.../configs/moe-m1-w13-n32
```

The tuned map is SHA256
`a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be`.
Its lookup must use logical expert count after placement. Keep all map entries,
especially the M>1 choices; do not silently substitute the modern wheel.

**Historical launcher and certified client.** Both live under
`experiments/qwen38-flash-next-fp8-b70/tools/`:

- [launch-tp4-mtp1-4352-ple-only-a367-fullgraphdet-w13n32.sh](../experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-mtp1-4352-ple-only-a367-fullgraphdet-w13n32.sh),
  SHA256 `5a23efc2d3b2ac73ea9f19c1e1ebaa28c8bb878838a09aeb40f3ab364e9817e7`.
- [run-tp4-mtp1-4352-ple-only-a367-fullgraphdet-w13n32-client.sh](../experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp1-4352-ple-only-a367-fullgraphdet-w13n32-client.sh),
  SHA256 `251db89c5e1eca8156dc92f8aa90cfee293805f2cbfe44b7319407aea38c685f`.
  This is the frozen certification-battery client; it checks supervisor/runtime
  identity, pinned quality/depth harnesses, canary and tuned-map selection.
- The record performance client is separately
  [wait-and-run-client.sh](../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/wait-and-run-client.sh),
  calling `scripts/bench-openai-realistic-suite.py` with the fixed
  `repro/rapid-model-snapshots-b70/realistic-suite-v1.json`, chat mode,
  max tokens 512, metric tokens 100, seed 20260609, temperature 0, top_p 1,
  thinking false and returned token IDs.
- The exact MoE selection verifier is
  [verify-moe-m1-w13-n32-selection.py](../experiments/qwen38-flash-next-fp8-b70/tools/verify-moe-m1-w13-n32-selection.py),
  SHA256 `c874852bbae20f4d738e1f3a37f1b16d553e50dc9e8c56c2b0caabc22675dc0e`.
  These three file hashes were checked during this survey; that is not a
  complete runtime or frozen dependency audit.

To reconstruct the record, restore the guide's source series, exact native
stage, oneCCL, environment and official model into separately admitted paths;
verify all identities; derive a new packet through
`rewrite-q38-a305-to-a364-native-exact-gdn-certification.py` for the battery
and `rewrite-q38-a306-to-a366-native-exact-gdn-realistic-suite.py` for the suite;
then use a reviewed cooperative supervisor. Preserve the historical packets.
**Do not execute `run-record-gate.sh` or `run-q38-a367-host-controlled.sh`:**
they invoke prohibited power/swap/page-cache operations and unsafe old cleanup.
The guide is explicitly `lab-replay`, not a validated fresh-host installer.
The publisher tree-metadata input, installable environment lock, complete
record-stage closure and independent replay remain open.

**Quality and promotion gates.** A364 passed the battery, A365 repeated it in
a fresh server, A366 repeated again; A367 supplied performance. Exact-2K token
hash is `afffd2110812762164862b6388f054bb56696ee57b07eadce411a702c40bc714`;
exact-4K is `1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc`.
All seven quality outputs match the authority, with the inherited semantic
code miss (6/7), 16/16 repeats and exact needle. All twelve record outputs
match the predecessor. Keep recovery canary, runtime/graph and tuned-map gates.

A new headline additionally needs the complete varied suite once per fresh
attempt, `cached_tokens=0` on every request, no prompt/KV/response/history reuse,
the unchanged target and verifier, repeat/fresh-server exactness, and the
[hash-bound promotion attestation](../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-promotion-attestation.json).
Report class-balanced rate, all-prompt diagnostic, p10/mean, TTFT, wall rate,
natural completion under 512 tokens, event/interval counts and hashes.
[check-replay-result.py](../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/check-replay-result.py)
compares saved suite hashes/booleans; it does not itself establish fresh-server
quality or current health. Measured 512-token one-user prefill remains absent.

### What changed after the record

| Date / evidence | Result and present meaning |
| --- | --- |
| September 13 [A394 teardown audit](2026-09-13-a394-teardown-audit.md) | Long-context rows passed, but supervisor rc143, mismatched stop protocol and cached health receipts did not establish clean shutdown. Historical freezes followed MTP-lineage teardown; telemetry and short gaps were suspects, not proven sole causes |
| October 8 [Screen 1 load failure](../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-08-screen1-mtp1-host-oom-result.md) | Modern V30 port exhausted host memory; fault preceded recorded OOM victims. No generation. A later bounded health pass did not qualify that configuration |
| October 8 [memory design](../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-08-host-memory-reduction-design.md), [calibration reconstruction](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/CALIBRATION.md) | Bounded mmap native-FP8 PLE rows, v5 expert placement and bounded loading were developed; exact-size pinned allocation removed about 24.249 GB of allocator padding in the attempt-7 budget. These are changes to an experimental runtime |
| October 8 [attempt 7 analysis](../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-08-attempt7-gpu-fault-analysis.md), corrected by [October 9 ordering](../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-09-attempt7-ordering.md) | Full TP4 startup dummy/profile forward faulted before completed KV initialization/capture. First CCS fault preceded recorded SIGINT completion and crash reports. Host-expert residency was a hypothesis; teardown, mmap reads and memory-watchdog kill were not established causes |
| October 9 [exit ownership audit](../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-09-exit-lifecycle-analysis.md), [teardown preparation](../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-09-teardown-patch-prep.md) | Tiny byte-correct gathers faulted near abrupt exit with both image and host UMD. An ordered cooperative teardown overlay was prepared, then applied with owner authorization |
| October 10 [immediate-exit reproduction](../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-10-exit-fault-reproduced.md) | Immediate abrupt exit after local-reference release faulted; orderly cleanup and ten-second-idle exit passed. One-layer mixed-host computation and teardown passed. Native queue/mapping cause and complete production lifecycle coverage remained unproved |
| October 11 [fourth incident closure](2026-10-11-fourth-incident-closed.md) | Startup routing returned padding IDs -1; the modern aligner omitted the negative guard. Fixed routing completed TP4 profile with 15,895 receipts/rank, zero boundary violations/new faults, four complete teardown receipts, container exit 0 and a clean 305-second watch |

The October diagnostic image was
`vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`,
V30 upstream `ced6857afa0ea7b2e3f0846a62e1394e90f15607`, Torch 2.13.0+xpu,
Triton 3.7.2+xpu, XPU kernels 0.1.14.1, with reviewed Python overlays.
It is **not A367**: different model implementation, GDN, compiler, collectives
and loader. The [runtime note](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runtime-notes.md)
records those differences. No modern-runtime result replaces 46.854250.

**Resolution is scoped.** The fourth incident's router-padding defect is closed.
The abrupt-exit class has a supported cooperative remedy and a clean TP4
startup proof. Attempt 7's initiating cause, full generation/capture exit
coverage and native mapping lifetime are not universally resolved. The October
11 proof bypassed warmup/capture and sent **zero generation requests**.
Host pressure peaked at 77.079 GB; availability fell 119.170 → 47.100 GB.
Calibration still returned `passed=false` because all four VRAM reserves were
unknown. None of these numbers calibrates A367.

### Safe-launch procedure for a later authorized window

There is no currently qualified turnkey replay. A safe procedure must retain:

1. Coordinator ownership of all four cards, no overlapping IQ3/LTX/model work,
   an unused evidence directory, current source/model/overlay seals, current
   health and memory/storage admission. Never infer idle state from this note.
   Keep at least five minutes stop-to-next-launch; the newer calibration
   supervisor uses **305 seconds**. No resident server or automatic restart.
2. For Screen 1b, the applied
   [teardown overlay](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-fix-teardown/README.md)
   is the sole cooperative worker exit: drain; release graphs/tables/UVA aliases;
   close PLE views/mmaps; release pinned owners and registries; release pools,
   workers and communicators; final device/host-cache drains and synchronization.
   Signals request cancellation and cannot interrupt cleanup. Require four
   ordered rank receipts, clean container exit and clean kernel postflight.
   Docker uses SIGINT and unlimited stop timeout; the controller sends one
   SIGINT and reports a 300-second overrun without forcing termination.
3. For the native certified recipe, use the separate packet-4
   [cooperative shutdown guard](../experiments/own-xpu-runtime/stage1/packet4-prep/driver/shutdown_guard.py)
   and [calibration supervisor](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/README.md).
   It waits for the whole launched session, not merely the API PID. The V30
   overlay cannot simply be copied onto the old source and called qualified.
4. Keep the [XPU-SMI bypass](../experiments/qwen38-flash-next-fp8-b70/tools/q38_xpusmi_bypass.py):
   no post-stop telemetry calls or polling loop. Its copied A146 receipts are
   **historical, not current health or current free VRAM**. The A394 audit
   explicitly found that false acceptance. Use passive journal/process evidence,
   admitted bounded health and supported memory counters; unknown means unknown.
5. First fault response, CAT error, engine reset, timed-out job or coredump stops
   new submissions and preserves the evidence. Never clear dumps/latches,
   retry a failed server, kill a busy group or reset/reboot automatically.
   Under the standing rule, a first fault permits one bounded health recovery
   probe in authorized device work; a failed probe or second fault stops work
   for the owner's reboot decision. The sealed calibration below is stricter
   about earlier boot faults: do not bypass its admission with a stale receipt.
   The [local recovery policy](../docs/local-ops.md#b70-xe-recovery-policy)
   supplies the evidence-first procedure. No recovery is authorized in this survey.

Screen 1b's separate load rules are 96 GB preallocation ceiling for the named
arm, 24 GiB available-host stop and 2 GiB reported-free-card stop; qualification
needs observed pressure ≤90 GB, plateau ×1.15 ≤90 GB and known ≥4 GiB free on
every card. These are **not** the native A367 calibration's thresholds.
The [October 11 do-not-repeat list](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/DO-NOT-REPEAT.md)
forbids replaying the unfixed router and using v5's load-only hook for generation.

## 2. Speed levers, ordered by likely return for the work

No new FP8 gain was measured here. The ranking is engineering judgment from
saved measurements; zero improvement remains possible. Small timing changes
need a complete-cycle benefit before they merit a full campaign.

**The old M=2 problem is partly solved.** [A344–A354](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-12-a344-a354-the-second-verify-row-is-gdn-glue.md)
measured 27.2 ms at M=1 versus 42.7 ms at M=2: **+15.5 ms**.
GDN's block rose 2.4 → 11.2 ms, **+8.8 ms**. These were diagnostic zeroing
arms with changed outputs, not speed qualifications.
[A361–A363](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-12-a361-a363-the-extension-exact-serial-mode-removes-the-tax.md)
moved exact serial rows inside the extension and reduced M=2 to **33.69 ms**.
A364–A367 certified that win. Preserve its BF16 state round-trip and completion
barrier; disabling the barrier had no measured benefit.

The later [A384–A386 decomposition](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-13-a384-a386-m2-remainder-decomposed-result.md)
accounts for 33.69 ms as MoE GEMMs 14.2, MoE glue/shared/collectives 4.7,
QSA 4.7, GDN 2.1 and about 8.0 ms remaining small-operation/launch work.
Sampler 0.89 ms and draft 2.22 ms sit outside that forward timer. Treat
subtraction results as diagnostic attribution, not additive guaranteed savings.

| Priority | Lever and expected benefit versus effort | Decisive evidence and IQ3 transfer |
| --- | --- | --- |
| 1 | **M=2 MoE glue and small-operation fusion.** Best chance of several tok/s; medium/high implementation effort. First demand roughly 2–4 ms of critical-cycle savings, not a tiny isolated kernel win | 4.7 ms MoE glue plus ~8 ms small operations remain. Attribute alignment/sort/quantization, shared expert, collectives and gaps per rank, then change one exact boundary. IQ3's busy/forward/hit/miss accounting prevents mistaking off-critical-path work for speed |
| 2 | **Memory headroom and expert placement.** No direct tok/s gain can yet be credited; high enabling value, medium effort and material host-memory risk | Near-full cards can block a better workspace/placement. Measure rank peaks and host pressure before moving rows. IQ3's memory proof unlocked a better split; its actual split and speed do not transfer to TP4/EP4 |
| 3 | **Adaptive MTP depth after cheaper verification.** Fixed MTP2 has negative evidence; adaptive gain unknown, low-cost acceptance analysis but substantial integration/gates | A387 is ~8–9% slower at exact 2K/4K despite holding pins; short high-acceptance rows were ~6% faster. Measure second-draft acceptance and complete M=3 cost per prompt class. IQ3 demonstrated why consecutive first-draft hits are not second-draft acceptance |
| 4 | **One-launch exact two-row GDN.** Small residual opportunity and high exactness effort; below broad glue work | Only ~2.1 ms GDN module remains, so the former 8.8 ms is unavailable. A multi-row kernel differed by one ulp; a correct candidate must preserve every intermediate rounding/state update. Apply IQ3 write-set proof and exact intermediate-state checks, not tolerance |
| 5 | **Prompt reading at the same 64-token arithmetic.** Potential large TTFT value; no supported decode tok/s gain; medium/high effort | A389's 512 batch reduced ~200 s to ~114 s at 32K but changed all depth hashes. Retain 64-token arithmetic while investigating launch fusion/host coordination. IQ3's removal of duplicate profiling is a method to check, not an assumed FP8 bottleneck |
| 6 | **Many users.** Potential aggregate throughput value, no single-user tok/s gain; high effort and unresolved output authority | A383–A393 mixed prefill/decode shapes and failed exact outputs. Run an operator shape census before any server localization. IQ3 per-rank attribution applies; two-card layer balancing does not cure batch-dependent collectives |

For priority 1, a rough **planning scenario**, not a prediction or benchmark:
using the diagnostic ~36.8 ms forward+sample+draft sum, saving 2–4 ms with
unchanged acceptance would scale 46.85 to about **49.5–52.6 tok/s**.
The real varied-suite cycle distribution is missing, so no such rate belongs
in results or a performance curve. A row-invariant collective alone has only
a measured 1.47 ms excess; simply disabling the selector changes the hash.
[A378/A379](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-13-a378-a379-row-wise-selector-cost-result.md)
already found that below their 3 ms selection bar. HC selector removal saved
essentially nothing. Keep these closed as standalone flag sweeps.

**Headroom versus KV/placement.** The
[result packet](../results/qwen38-flash-next-fp8-b70/README.md#2026-09-13-the-promoted-mtp0-line-at-32k-input-lossless-within-the-line-lab-measured)
records cards within **0.1–0.35 GiB of full** before the long-context placement
extension; this is historical context, not four current free-memory readings.
A367's entire KV allocation is only **0.350708 GiB/rank**. Reducing it cannot
create several GiB of reserve and would reduce admitted context. Keep BF16;
compressed KV is excluded. A381/A382/A394 instead used **1,341,530,112 bytes**
of KV and a wider never-hit/max-count-2 expert map (3.57–3.97 GiB host rows/rank).
That enabled exact 32K rows, not a proven short-suite speed win. Every offloaded
expert remains callable; unfamiliar prompts can incur UVA traffic. Do not
optimize placement by selecting only friendly prompts or drop expert weights.

A367's recovered host trace shows **115.869876 GB availability decline**.
The 63.609487 GB identified pins include 51.200246 GB native-FP8 PLE, 11.137843 GB
expert rows and 1.271398 GB embeddings. The residual is not proved allocator
overhead, and device-labelled UVA is not another device table. The V30
mmap/allocator improvements cannot be subtracted from A367 without matched
measurement. IQ3's write-set-exact snapshots suggest inspecting live-byte
lifetimes and actual speculative writes; they do not establish that vLLM
duplicates the same 343 MiB snapshots.

**MTP depth and broader September follow-ups.** [A387](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-13-a387-mtp2-exact-mode-screen-result.md)
closes unchanged fixed MTP2; do not reopen a depth sweep without a changed
verify-cost model. Retain target verification and state restoration on hit,
miss, cancellation and request boundaries. [A389](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-13-a389-32k-prefill-batch-512-result.md)
is an output-changing candidate, not a lossless prefill upgrade.
[A393](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-13-a393-row-wise-selector-shape-log-result.md)
shows why selectors above two catch prefill tails and why simply increasing
max sequences fails. Any proposed new arithmetic authority is the owner's
quality decision. The September closeout also leaves the frozen long-context
quality battery, clean deployment and independent replay open; A382/A394's
four-row medians at 8K/16K/32K are 42.7035/45.5645/44.052 tok/s, separate
capacity measurements, not replacement record-suite scores.

**What to carry over from today's IQ3 work.** The
[device ledger](2026-10-14-packet45-device-qualification-rounds.md) and
[SPEED2](../experiments/own-xpu-runtime/stage2/packet45-merged3/SPEED2-CLOSEOUT.md),
[SPEED3](../experiments/own-xpu-runtime/stage2/packet45-merged3/SPEED3-CLOSEOUT.md),
[SPEED4](../experiments/own-xpu-runtime/stage2/packet45-merged3/SPEED4-CLOSEOUT.md)
record attribution, exact write-set backup, single-owner event accounting and
confirmed-redo restoration. They also show an optimized kernel can lose at the
pipeline level, and reduced copied traffic can give no cycle benefit (SPEED7).
The owner reports over 20 fault-free device launches today; the retained ledger
supports repeated clean work but is not an FP8 health qualification.

Use the same decision discipline: short operator gate, then exact endpoint
gate, then matched **fresh-process A–B–A**, with unchanged prompts, configuration,
dispatch and output hashes; more than one fresh server per speed verdict.
Record hit/miss probabilities, accepted tokens per cycle, critical-rank busy
time, restore/redo, waits and total cycle. Avoid duplicate synchronous profiling
and keep instrumented runs out of speed headlines. Reject parity/noise and
incomplete controls; IQ3's SPEED6 interleaved packet44 control stopped at 8/12,
so it is not a template for claiming a complete A–B–A pass. IQ3's 128-token
scope exception and two-card 39.422009 tok/s result confer no FP8 promotion
authority. FP8 retains its full 512-cap varied suite.

## 3. The single first device step

**Select one native A367 load/capture/clean-exit calibration, with zero
generation requests, once its admission blockers are resolved.** It answers
whether the owner's chosen arithmetic can load and leave this host safely,
and measures the missing matched memory need. Its direct speed gain is zero;
its value is avoiding an unsafe full benchmark or optimizing the wrong runtime.
The experimental mmap line's next generation screen remains documented in
CURRENT; it is not a prerequisite for the owner's return to A367.

The existing exact entry point is
[a367_calibrate_load.py](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/a367_calibrate_load.py),
with [preregistration](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/preregistration.json)
and [runbook](../experiments/own-xpu-runtime/stage1/packet4-prep/WINDOW-RUNBOOK.md#october-11-addendum-certified-a367-calibration-comes-first).
This is a **future command only; not run or queued**:

```bash
taskset -c 4-15,20-31 nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/a367_calibrate_load.py \
  --execute \
  --owner-window "${OWNER_WINDOW:?current admitted calibration window}" \
  --health-receipt "${HEALTH_RECEIPT:?fresh same-boot four-card receipt}" \
  --payload-receipt "${PAYLOAD_RECEIPT:?verified exact launch-path payload}" \
  --output "${CALIBRATION:?new absolute evidence directory}"
```

All four values must come from the coordinator's new admitted window.
No old receipt or newly invented approval is supplied here. Long native work
must be owned by a coordinator-managed durable user unit under the standing
process rule; the old packet's durable-terminal example does not authorize
running it in an agent shell or installing/starting a unit during this survey.

**Pre-device blockers are real, not paperwork to bypass:**

- The existing default starts only with **120,000,000 KiB available**. The
  packet documents why that refused this host and provides a separately
  owner-approved, hash-bound calibration-only exception. A lower floor cannot
  be inferred from the mmap run. The live **12,000,000 KiB** reserve stays.
- Require current boot/halt resolution, exclusive ownership, 305-second
  previous-stop gap, a passing four-card receipt ≤600 seconds old, the exact
  owner-window/seal and no disqualifying fault latches. The original driver
  rejects earlier boot faults; today's IQ3 success alone cannot satisfy it.
- Resolve the documented historical model-receipt mismatch. Full payload
  verification must be ≤1 hour old and bind the **actual launch path**.
  The script hard-codes the USB model at
  `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`; an NVMe-only receipt
  is insufficient. No model hash/read was performed for this survey.
- Source defaults include `/home/steve/src/vllm-current-main`; native stage
  defaults include the USB exact-GDN stage. Treat the source as protected,
  not as permission to clean, checkout or restore it. Establish an authorized
  clean, pinned reconstruction and review/reseal any path changes first.
  The rescue archive remains untouched and is not required by the command.
- The packet requires **60 GiB free** on its output filesystem. Root has
  only 24.27 GB; it is presently blocked there. Do not reduce that floor,
  borrow another lane's smaller build allowance or use the failing RAID.
  Admit every cache/trace/output filesystem and peak writes before launch.

The supervisor checks the 75 patch/bundle members, source files, 18 stage
members, collective/runtime pins, map and model metadata, then rechecks health
and admission after the audit. It restores original FULL_DECODE_ONLY capture
[1,2] and MTP1 selectors; it does not run the historical host-control wrapper
or the experimental mmap overlay. OMP=2 versus historical 1, cooperative
cleanup and new evidence paths are declared deltas, not an unchanged speed replay.

Allow **45 minutes for this one calibration** after payload hashing and
preparation: about 6 minutes admission/prior gap, 2 bounded health, up to
20 load/plateau, 5 graceful teardown, 6 post-exit watch, 6 contingency.
The plateau is 20 seconds, samples every 0.5 seconds, gaps ≤1.5 seconds.
Readiness only calls health/model-list endpoints. A fault, memory breach,
watch failure, stale/revoked window or failed gate requests one SIGINT.
Success needs complete rank/cgroup samples, preserved reserve, all session
processes gone, clean fresh journal and the 305-second post-exit watch.
A 300-second teardown overrun fails and waits without kill escalation.

A pass produces **startup-memory and exit evidence only**. It grants neither
a speed claim nor a floor change. The follow-up CPU derivation proposes
`ceil(observed availability decline / 1024) + 12,000,000 + 8,388,608 KiB`;
review and owner acceptance remain separate. Only then schedule the frozen
exact-output battery, fresh-server repeats and a fresh full suite; per-rank
VRAM and generation peaks still need evidence. This survey does not prepare
or launch a second device step.

## 4. Risks and preservation

- **Host faults:** the [stability guide](../docs/host-stability-and-fault-diagnosis.md)
  records bad non-ECC RAM, fenced blocks 53–57, GPU/GuC incidents and silent
  freezes. Preserve approved workarounds. One clean startup and the IQ3 streak
  do not certify all FP8 allocations, collectives, graph capture or exits.
  No power, memory/swap, service, driver, firmware or reboot changes here.
- **Protected dirty work:** [CURRENT's protections](../CURRENT.md#additional-preserved-work-and-operational-guards)
  cover the Flash-Next source and frozen runners. Do not touch
  `/home/steve/git-archives/flash-next-rescue-20261007/`, reuse a dirty source
  tree for a build, clear old STOP/FAULT files or run searches whose process
  command lines mimic the protected runners. This survey read tracked notes
  and code only, preserving existing lane files and raw run directories.
- **Root capacity:** a read-only `df -B1 /` during this survey reports
  **24,273,293,312 bytes free (24.27 GB / 22.61 GiB)**, 98% used.
  This is below CURRENT's 50 GiB reserve and the calibration's 60 GiB reserve.
  The IQ3 ledger records ~896 MB per chain and multi-GB retained packets;
  compiler outputs, caches, traces and model copies can exhaust this quickly.
  No build, archive, cleanup or model copy is part of the return survey.
- **Failing RAID:** passive mount metadata identifies **/dev/sdb2 →
  /mnt/raid-models**; a bounded current-boot kernel query records
  `Buffer I/O error on dev sdb2` at logical block 36 on October 15
  09:39:10–09:39:20 EDT, and block 674294928 on October 14 21:09:59 EDT.
  Do not read/repair/remount it or place weights, native libraries, caches,
  receipts or backups needed by the return on it. The documented calibration
  defaults use root/NVMe and **/dev/sda2 at /mnt/usb-models**, not sdb2.
  Before later admission, prove real paths do not symlink onto RAID; this
  survey deliberately did not traverse either model store. Historical advice
  to remount sdb2 after reset is not current operating guidance.

Validation for this note is limited to source/receipt cross-checks, the three
historical file hashes above, relative-link existence and whitespace checks.
No fresh performance, exactness, health, complete dependency closure or safe
launch is claimed. Commit and push only this note on main, preserving all
existing tracked/untracked work.
