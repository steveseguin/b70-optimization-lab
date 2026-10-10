# First native window — conditional preregistration, not launch authorization

**DO NOT LAUNCH from this packet yet.** The CPU transport is tested; the
certified environment and native bindings are not ready. The requested
“certified vLLM XPU image used by the 46.854250 line” does not exist in its
retained identity: A367 used a host venv and its guide calls the container
route unbuilt. No command below supplies a missing certification. The host
halt also remains in force. Resolve these before booking GPU time.

## Identities that must not be mixed

| Component | Exact retained identity |
| --- | --- |
| A367 model | `Qwen/Qwen3.8-Flash-Next-FP8`, `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` |
| A367 environment | Host Python 3.12 venv; torch 2.11.0+xpu; Triton 3.7.0; oneAPI 2025.3; **image digest: absent** |
| A367 vLLM | Public base `76cfe1cd88d30d525eec8be5bff75f8b77471c88`, overlay `6d8724577dabbee5fa0bbc70c4d927c6174c8d8a` |
| A367 kernels | Served 2f829747 stage, replacing only `_xpu_C.abi3.so` with `bbae3c59e226c1b0c2a2dca6c51b4465cf36fd26` over `e421889999bc1e5a5f11044d14548b9afdba644d`; replacement SHA256 `6b95dc90c25bb0f9c2503805e4184648ddcac089ec54ec65fe7eeb13ab2b097b` |
| A367 oneCCL | `4ceafd1`; libccl `43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700`; kernels.spv `0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9` |
| A367 topology | TP4/EP4, BF16 activations/KV and inter-row recurrent state, MTP1, 4,352 capacity, 64-token prefill chunks; original capture sizes 1 and 2 |
| Reopen candidate image | `vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9` |
| Reopen sealed overlay | manifest SHA256 `e00bb55d8378ecd0065e82a8c3b6fdd59268bd33aae6e0f356ca48f067926f2d`, upstream `ced6857afa0ea7b2e3f0846a62e1394e90f15607`, head `9d79d28d7e32f33bdbd115c85d116583ce679cb6` |

The [audit](comparator-identity-audit.json) pins all five A367 series seals:
lossless-MTP1 `1b2a17c1`, placement `005dc578`, Triton-HC `62219122`, fused-QSA
`6d872457`, and exact-serial-GDN `bbae3c5`. All **75 seal members match**.
The kernel base also needs the certified `2f829747` history plus the eight
later kernel commits to `e421889`, as the linked kernel series records; do
not apply just the final two patches onto arbitrary upstream. Do not run
historical replay wrappers: they change host settings forbidden today.

The 27B lane has a *separate* package image:
`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a`.
That is the R312d-c package launcher pin, not an A367 image or automatic
binding of every historical 27B oracle. Its exact payload, launch/profile
diff, kernel binaries and source overlay must be admitted separately. Use
27B's FP16 activations/KV and FP32 recurrent state, never Flash's BF16 state.

## Work that must be finished on CPU before the window

1. Choose the retained A367 host environment or produce an independently
   qualified container receipt. Do not relabel the reopen image. Its full-model
   memory fit, output parity and teardown are still open, even though its
   single-layer probe passed. Resolve storage and current host halt separately.
2. Implement and review the native `driver-27b.py` / `driver-flash-next.py`
   adapters. They are **not delivered in this packet**. Bind every module,
   function alias and native argument layout to a source SHA256, original
   dispatch, layer/rank and touched state indices. Inventory all production
   projection shapes from packet 1, rather than treating a visited subset as
   complete. Do not execute external model code during this CPU review.
3. Supply the driver protocol described below, plus the identity/authorization,
   payload, source, library/kernel, health and binding manifests. They must
   reject unavailable shapes and unseen aliases before loading weights.
   Fixture operators that have no CPU equivalent stay UNTESTED. The Flash
   CPU reference does not reproduce Triton activation quantization or the
   complete PLE injection, and neither reference implements MTP rollback.
4. Prove eager neutrality as a separate gate. A367's certified graph setting
   cannot coexist with these host-read hooks. Turning off graphs is a declared
   diagnostic identity change, not an already-proven neutral change. The
   first window compares one fixed prompt with its frozen full token array;
   all twelve plus same/fresh-process controls are required later.
5. M1/M2/M6 are census targets, not authorization to change certified
   scheduling. Record only naturally observed actual row shapes. A367's MTP1
   verifier is M2; M6 may be absent. Do not increase row-wise selectors beyond
   2, increase draft depth, concatenate unrelated prompts or slice a captured
   result and call it an M6 dispatch. Missing M6 requires a separately
   preregistered operator replay after this screen, with no speed claim.

The driver uses `run(args, Recorder)` in the admitted environment. It validates
live engine config, disables compilation/capture before model construction,
installs graph entry-point refusal, then installs read-only bindings in every
worker. It executes the fixed prompt once, greedy, natural 512-token cap, with
no prefix/KV/response/history reuse. Collect actual token IDs outside all
operator calls and call `finish(ids, cached_tokens=0)` on each rank's recorder.
Use one output directory per rank, with a **shared 8 GiB total disk budget**
(2 GiB per Flash rank). Do not repeat shared model weights in every fixture:
the present transport does not deduplicate them, so the production binding
must preregister a smaller sampled boundary set or increase the admitted disk
cap honestly. A cap failure is incomplete evidence, not a pass. A complete
all-layer/all-family census will likely need a later, larger disk budget.

In `finally`, quiesce, finish queues/collectives, drain and release views before
backing, then contexts; preserve a structured teardown receipt. A timeout
cooperatively cancels admission, never calls `_exit`, hard-kills or retries.
The supervisor owns journal polling from before construction, memory guard,
fault abort, signal forwarding, all stage exit codes and external postflight.
Long native work belongs in its own user unit with SIGINT and SendSIGKILL=no.
This packet does not install a unit or supply that missing native driver.

## Ordered command transcript after those gates are closed

These are **conditional command forms**, not a runnable completed campaign.
`WINDOW`, `COMPARATOR_PY`, `HEALTH_PY`, and the source-bound drivers/identities
below must come from the reviewed window admission. There is intentionally no
fabricated Docker launch with the wrong image. Inside a later certified image,
the extraction CLI invocation is the same, with repository mounted read-only,
an admitted writable fixture directory and only the selected model mounted
read-only. No image pull, package install or weight download belongs here.

1. In the exclusive window, the coordinator records owner authorization, host,
   boot, selected PCI IDs, memory/disk limits and previous completed stop time.
   Preserve any FAULT/coredump evidence. Check actual owners before native work;
   never operate LTX units or port 8188. Wait **at least 305 seconds since all
   previous native owners finished teardown**. A passing health receipt does
   not waive the gap or a halt. Set both interpreters to the admitted paths.

   ```bash
   export OMP_NUM_THREADS=2
   nice -n 19 env OMP_NUM_THREADS=2 "$HEALTH_PY" -B experiments/ltx25-b70/scripts/check-four-card-health.py "$WINDOW/health-before.json"
   ```

   This bounded health script itself uses the GPUs, so it is listed only for
   the authorized window; it was not run in this preparation. Require all four
   cards and no new journal faults, matching host/boot and fresh timestamps.

2. The preregistered supervisor starts the admitted 27B extraction **only if
   its complete official payload is already present and hash-verified**. If
   absent, record SKIPPED-WEIGHTS-ABSENT and do Flash only. No download, swap
   change, cache drop, power change or driver reset. The 27B command form is:

   ```bash
   nice -n 19 env OMP_NUM_THREADS=2 VLLM_XPU_ENABLE_XPU_GRAPH=0 "$COMPARATOR_PY" -B experiments/own-xpu-runtime/stage1/packet4-prep/extract_fixtures.py --model 27b --driver "$WINDOW/driver-27b.py" --identity "$WINDOW/identity-27b.json" --prompt-id incident-retrospective --output "$WINDOW/27b" --max-bytes 8589934592 --chunk-bytes 1048576
   nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet4-prep/compare_fixtures.py "$WINDOW/27b" --max-bytes 8589934592 --output "$WINDOW/27b-comparison.json"
   ```

   Retain comparator exit status and teardown receipt before comparisons. The
   CPU comparison may follow clean comparator shutdown; no server is kept for
   it. If 27B ran, wait another 305 seconds after completed teardown before
   Flash. CPU comparisons can occupy that gap.

3. Flash extraction in its **admitted comparator environment**, with the
   same selected fixed-suite prompt and its Stage 2 oracle. The native driver
   must provide per-rank subdirectories; the root is a fresh directory owned
   by that driver. The total budget below is divided among four rank writers.

   ```bash
   nice -n 19 env OMP_NUM_THREADS=2 VLLM_XPU_ENABLE_XPU_GRAPH=0 "$COMPARATOR_PY" -B experiments/own-xpu-runtime/stage1/packet4-prep/extract_fixtures.py --model flash-next --driver "$WINDOW/driver-flash-next.py" --identity "$WINDOW/identity-flash-next.json" --prompt-id incident-retrospective --output "$WINDOW/flash-next" --max-bytes 8589934592 --chunk-bytes 1048576
   for rank in 0 1 2 3; do
     nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet4-prep/compare_fixtures.py "$WINDOW/flash-next/rank-$rank" --max-bytes 2147483648 --output "$WINDOW/flash-next-comparison-rank-$rank.json"
   done
   ```

   Compare exits 1 for a difference or untested boundary; the supervisor
   records every comparison status and collects every rank, then prohibits
   qualification. It does not restart the comparator. A recorded numeric
   difference alone is not a GPU fault. A fault or failed teardown prevents
   the smoke below until the owner/recovery rules allow further native work.

4. After complete comparator teardown and external idle/clean-journal evidence,
   record the stop time; leave **305 seconds before the native smoke**. Build
   under the admitted window directory, not a shared runtime tree:

   ```bash
   nice -n 19 env OMP_NUM_THREADS=2 cmake -S experiments/own-xpu-runtime/stage1/packet3-prep -B "$WINDOW/native-build" -DOWN_RT_HOST_ONLY=OFF -DOWN_RT_BUILD_NATIVE_SMOKE=ON
   nice -n 19 env OMP_NUM_THREADS=2 cmake --build "$WINDOW/native-build" -j2
   nice -n 19 env OMP_NUM_THREADS=2 "$WINDOW/native-build/own-rt-smoke" --enumerate --card 0 --receipt "$WINDOW/native-smoke.json"
   ```

   Use card 0 only if its physical PCI mapping matches the admitted card.
   The smoke's own cooperative shutdown must finish before it exits. A refusal
   holds resources for its supervisor; do not turn a timeout into SIGKILL.

5. Save full kernel journal boundaries, process exit and device idle evidence,
   then the fresh bounded health receipt. Leave cards empty; do not restore a
   server. The next model launch, even by another lane, waits 305 seconds from
   the latest completed teardown. Preserve all fixtures and failed evidence;
   delete only this campaign's build scratch after recording binary hashes.

   ```bash
   nice -n 19 env OMP_NUM_THREADS=2 "$HEALTH_PY" -B experiments/ltx25-b70/scripts/check-four-card-health.py "$WINDOW/health-after.json"
   ```

## Pass criteria and time budget

This first window passes only its **diagnostic extraction** gate when the
entire selected token array equals the frozen oracle, cached_tokens=0, every
expected visited operator has a valid hash-bound fixture or an explicit
unobservable/missing-shape entry, all rank receipts agree, caps hold, and
teardown and journal postflight are clean. Record differences for each U-row;
no tolerance changes or waiver. A missing operator/state binding makes the
all-family extraction incomplete even if every recorded sample is exact.
No CPU mock result, schema pass or single-prompt match qualifies packet 4.

The resource smoke independently requires two changed 4 KiB round trips
byte-exact, peak 4,096 device bytes plus 8,192 pinned bytes, one owned in-order
queue, no in-flight events/live allocations, final marker complete,
safe_to_exit=true, orderly context release and zero new fault-class lines.
Preserve its binary SHA256, compiler, census and validated teardown receipt.

Plan **60 minutes for Flash-only**, **85 minutes with 27B**. These are
preregistration limits, not observed runtimes:

| Flash-only allocation | Minutes |
| --- | ---: |
| Initial stop gap, admission and health | 5 |
| One load and one prompt extraction | 15 |
| CPU reference comparisons | 10 |
| Graceful model teardown and evidence | 5 |
| Stop-to-smoke gap (CPU work may overlap) | 5 |
| Native build and smoke | 5 |
| Final health and evidence closure | 5 |
| Reserved time for slow I/O/cleanup | 10 |

Adding 27B reserves 15 minutes extraction/comparison, 5 minutes cleanup and
5 minutes stop gap. If loading/extraction exceeds its budget, request
cooperative stop once and retain partial evidence; no retry. Cleanup may run
past the nominal budget if needed to avoid an unsafe forced exit. A full
12-prompt/two-fresh-process census needs a separate budget after this screen.

Record model/config/tokenizer/shard hashes, source/dirty delta, exact image
or host environment, all patch seals and binary hashes, library/compiler
versions, host/boot/UMD/firmware/PCI IDs, rank/placement, sampler/MTP settings,
flags/env, prompt/suite hashes, complete token arrays, cache count, actual
M/N/K/rows, every tensor/state hash, disk/host/device peaks, time spent,
missing bindings, differences and all start/stop/fault receipts. Do not time
the hooked path as a benchmark.

## Measurement traps read for this preparation

The [host-read/capture and H2D diagnosis](../../../ltx25-b70/notes/vae-graph-capture-blocked-01.md)
shows that a device scalar read inside capture produced an absurd allocation,
and captured H2D operations retained pointers to temporary host buffers. This
tool never captures, never creates H2D inputs, and refuses capture entrypoints
when the reviewed driver installs the guard. Its D2H readback is explicitly
eager diagnostic overhead. The [profiler note](../../../../notes/2026-05-13-minimax-profiler-and-triton-attention.md)
explains why profiled timings are not benchmark rates; the same restriction
applies to these serialized host-read fixtures. No profiler is used here.
