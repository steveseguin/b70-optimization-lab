# Proposed49-frame qualification after107b

Status: CPU plan/runtime implementation and independent review complete. No
materialized successor packet,49-frame request or application reload yet.
107b remains healthy and idle; its
consumed57-request plan and frozen25-frame pools must not be extended.

The valid107b trace closes direct-static activation-copy reuse: its measured
allocation/fill envelope is too small. The next useful scope is49-frame clips at
640×384. This is capability/scaling qualification, not a demonstrated speed
optimization. Longer clips may amortize fixed work but can increase attention,
decode cost and latency. No speedup is assumed. Historical`timed-49` filenames
are request indices; two independent source/history audits found no49-frame
qualification. Do not reopen decoder graphs, chaining, generic QKV fusion or a
blind placement/worker sweep on this evidence.

## Fixed quality and geometry contract

Retain the pinned distilled BF16 checkpoint,8+3steps,24FPS playback, window64,
W2/B1/shared pool,23/25 block placement and native/replica decode. Every new
reference must execute at49frames. A25-frame prefix is not an oracle.

| Tensor/signature | Source-derived expected shape |
| --- | --- |
| Stage A video latent | `[1,128,7,6,10]` |
| Stage B video latent | `[1,128,7,12,20]` |
| Video graph tokens A/B | `420 / 1680` |
| Images | `[49,384,640,3]` |
| Audio latent | `[1,8,51,16]` |
| Waveform | `[1,2,96480]` at48kHz |

Temporal video size is`(49-1)//8+1=7`, from sealed
`source/comfy_extras/nodes_lt.py`. Confirm actual first-native tensor headers;
source-derived expectations are not measured qualification.

Audio comes from the protected checkpoint's metadata, not doubling the old
dimensions. The independent audit read only its199,664-byte header:
`/mnt/fast-ai/llm-models/LTX-2.5-baseline/vae/ltx-2.5-audio-vae-bf16.safetensors`.
HeaderSHA`5728d7b5855767302dc02161036620a4d50d8352ef6930a09de967ddd9e5e9a0`.
Existing model-verification ledger binds the full checkpoint to
`c52733d37f6a7fb7949c3dc0fb468c6cb2169e4d836983a73babb9f0d54837a5`;
the audit did not reread the whole model or load it.

The config specifies16kHz, hop160, latent downsample4, height causality,8 latent
channels,64 mel bins and stereo output. Hence latent rate25/s and
`round(49/24*25)=51` latent time positions. Causal mel length is`51*4-3=201`;
the configured vocoder multiplies length by160, and its bandwidth extension
maps16kHz to48kHz: `201*160*48000//16000=96480`. This also reproduces the
existing26→101→48480 contract.49frames/24FPS is2.0417seconds, while audio is
2.01seconds: do not silently pad, trim or stretch native output.

Sealed107b source references under its`source/` directory:

- `comfy/ldm/lightricks/vae/audio_vae.py`: latent factor at14, causal target at170,
  frame conversion at182, channel/frequency fields at209/213, rate at217.
  SHA`ba5a99f1573e12a9cff4b7ce0b3126afe374476d835ba3c04dc6a2e62ab3162c`.
- `comfy/ldm/lightricks/vocoders/vocoder.py`: configured stride/kernel at468,
  sample rates at672, source/output lengths at698–701 and final trim at712.
  SHA`2030bc1b2ad541ae8a0f14b7a52d7383460b70685cb4bd81724915728b39bd08`.

## Implementation boundary

Use one immutable duration contract with a new qualification ID and namespace;
retain strict25-frame historical guards in sealed predecessors.

1. Change both node356`length` and node366`frames_number`, including worker
   capture/setup graphs. Keep node365 conditioning and24FPS metadata.
2. Update geometry helpers, probes and receipt identity. Current
   `ltx_output_size_98.py` assumes temporal4, images25, audio26 and waveform48480.
3. Admit precisely the two new stage signatures per actual worker/device;
   retain all four ABAB eager/replay/repeat chain checks. Current
   `setup_gates.py` expects240/960 video tokens and26 audio tokens.
4. Update all four reference shapes and a bounded160MiB evidence-reader cap;
   the old90MiB cap cannot hold the49-frame image tensor alone. Continue full
   byte equality, finiteness, source/fixture/identity and native-repeat checks.
5. Remove107-specific sparse-trace overlay, job admission, lifecycle hooks and
   gates explicitly in the new builder. Merely disabling new job names is not
   sufficient. Preserve the corrected graph-node wrapper registration.
6. Use49 generated frames per completed clip in throughput accounting, while
   playback stays24FPS. Keep latency and throughput separate.

## Bounded experiment and resource admission

Propose the established57 requests:20 native executions,14 candidate,14 timed
and9 setup,50 charged capture maximum. Add a barrier after the first planned
native result: actual shapes/audio/finite tensors and measured headroom must
pass before a second native request. This result remains one of the20, not an
extra warmup. No new tracing campaign is needed.

Then require independent49-frame native repeats, all four complete tensors exact
on candidate and timed outputs, both worker capture admissions, chain checks and
decoder-replica parity/headroom. Stop on mismatch, nonfinite output, unexpected
signature/recapture, ownership change, memory/storage refusal, fallback attempt,
OOM or device fault. No retries, cache drops, eviction or tiled fallback.

107b's25-frame freeze had7.204/11.989/9.741/14.740GiB free on cards0–3. This is
context, not a49-frame peak bound. The VAE estimate rises1.556→2.724GiB, but does
not prove coexistence/peak behavior. Reassess native pre-admission, each captured
worker, decoder replica and chain scratch separately. Preserve the2GiB measured
post-operation floor; token ratios cannot substitute for memory qualification.

Four predicted F32 tensors contain146,164,992bytes/capture. Fifty captures need
7,308,249,600bytes=6.80634GiB before headers. Adding1GiB cache,512MiB previews and
192MiB logs/metadata gives8.49384GiB: propose9GiB runtime allowance above the
unchanged50GiB reserve, plus separate384MiB construction admission. Confirm
capture/preview counts and all output paths in the executable plan.

Current filesystem has51.959GiB available. A hypothetical later stopped-owner
107b exact-duplicate retirement would reclaim about2.780GiB and still leave a
4.636GiB shortage against9GiB runtime +384MiB source +50GiB reserve. Live107b
archives remain protected. Bounded storage review found no substantial disposable
cache: previous package/compiler cleanup already occurred, and preserved research
archives must stay. No raw hashes were refreshed or deletion performed.
No launch until genuine headroom is established; do not lower the reserve or
discard models, failed experiments or unique research to fit the plan.

Report nine intervals across ten scored clips, generated FPS, complete-clip
latency and bounded resource observations. This finite screen does not establish
endurance, robust tail latency, coherent streaming or visual quality by itself.

## Selected next step: explicit three-fixture resource pilot

The full ten-fixture qualification above is storage-blocked. Two independent
reviews support a narrower resource/capability pilot, without adopting its path
as fully qualified. Select the original boat, marble and bird fixtures explicitly.
Use6 native executions(two independent repeats each),7 candidate requests(four
fills andthree scored),7 timed requests(four fills andthree scored),9 setup:
29 total. All four complete tensors must match the new same-length native oracle.
The first native shape/memory barrier and both capture/decoder admissions remain.

**Capture cap is22, not16.** Existing guards charge every capture-bearing graph,
including pipeline fills:6+7+7+2. Do not suppress fill evidence or change that
accounting. Budget conservatively for14 full-output archives(6native+3candidate+
3timed+2setup), plus8 bounded placeholders. Each full archive is charged
146,164,992 payload bytes plus65,544 header bytes; each placeholder is charged1MiB.
Together with1GiB cache,512MiB previews and192MiB logs, this is3,867,555,440bytes
=3.60194GiB, leaving427,411,856bytes within a4GiB allowance. Exact role/shape/byte
bounds must be enforced before writing. This is a proposed conditional budget, not an
admitted runtime. Fresh checks still precede construction and launch.

The independent source check confirmed placeholders use images`[1,8,8,3]`,
waveform`[1,2,8]`, and existing latents. Largest49-frame F32 latent shapes above
give887,104 payload bytes; even65,544 header bytes yield952,648bytes, below1MiB.
Pinned107b`source/scripts/pipeline_decode_node.py`lines514–518 and590–592 implement
these placeholders(SHA`e7bdab34f213bb879192316ce6523f66758f88bde72c66d8bab6cc163eb8c825`).
`source/scripts/capture_node.py`lines39–60 saves all four fields, including fills
(SHA`6495b0c4de7ac054e35a39fb00e7c7b979d5fb51d6e77bc0dee18bad9d0ec9da`).
The decoder comment about skipping placeholders does not suppress capture files.

After hypothetical verified107b retirement and384MiB source allowance,4GiB would
leave about50.364GiB. No retirement/reload is authorized by these arithmetic
observations alone: root must preserve stopped-owner/full-proof/whole-file hash/
restore-map checks. No cleanup has occurred.

Three timed outputs provide onlytwo completion intervals. Preserve each interval,
latency and memory observation; no p95, speed-gain, record, full-suite quality or
adoption claim. A standalone CPU plan is being prepared under
`recovery/20261007-duration108-plan/`; runtime integration and resource admission
remain future work. Existing25-frame proofs and guards remain unchanged.

## CPU implementation and reviewed operating thresholds

The standalone plan passes 27 tests. Its exact pins are:

- Plan: `942407a8b46992e6887bb76ad2447f78f4ecd891ef89af91052235b8367214e2`.
- Qualification: `8fe720a6b3a7b838b28e5e745ec0763937c9cf5cda467998f259f4675570c1cd`.
- Schedule: `e0fbaa81c6879ddcfb20a9a2924f7534847090d4537e88e46089ec16867981a1`.

The new author runtime is `recovery/20261007-duration108-runtime/`. The old 107
author directory and sealed sources are unchanged. The builder preserves the
qualified 99b graph-node wrapper and removes 107 tracing. Frame metadata binds
49 across text, sampler, decode and setup receipts. Decoder qualification still
uses ten seeded probes. Capture serialization's Python wrapper and native library
are added to runtime identity and rechecked at launch. Shape, role and byte
reservations precede directory creation and save.

Capture order is six native, two setup, seven candidate and seven timed. Setup
may emit exact placeholders but is charged as full. Durable reservation
checkpoints require 6/15/22 ordered completed captures at the quality barriers.
Bank their separate hashes in closeout; they prove storage accounting, not
numerical equality. Each later native request rehashes the first archive,
metadata, memory receipt and admission barrier before running. The first barrier
checks full actual tensors, strict determinism, sample rate and memory receipt
request/plan/runtime/phase/fault identity plus the 2 GiB floor. Full native repeats
and optimized equality remain mandatory separate gates.

Independent review selected these pre-operation allowances in GiB, card order
0/1/2/3:

| Operation | Required free memory |
| --- | --- |
| Each native request | 8 / 8 / 2 / 9 |
| Either worker capture | 7 / 7 / 2 / 9 |
| Decoder preparation/probe | 2 / 2 / 10 / 9 |

Replica after-build admission rises from 5 to 8 GiB. Its internal post-probe floor
rises from 1 to 2 GiB, matching the outer gate. Chain checking uses actual slot
sizes plus duration-scaled scratch allowance, now with a 2 GiB pre-check margin
instead of 0.5 GiB; fresh post-check floor and residency checks remain.

These are engineering allowances, not proven 49-frame peak bounds. In 107b,
capture0 consumed 0.507/0.431 GiB and capture1 consumed 0.423/0.353 GiB on the
sampler cards. Retaining 7 GiB before worker1 leaves 5 GiB above the floor without
pretending static weights scale with duration. Replica build consumed about
1.729 GiB, then probing reduced physical headroom by another 3.387 GiB, motivating
the stronger decode guards. Native 8 GiB can bind after the first request: the
25-frame post-native primary reading was 8.124 GiB. A refusal requires review,
never automatic guard reduction or model eviction.

Validation: 285 full-runtime CPU tests passed in 21.306 seconds before durable
capture checkpoints were added. The updated 42 integration controls then passed.
Finally, 60 builder/integration controls passed in 1.997 seconds after actual-venv
preflight caught and fixed a private adapter API assumption. The failed line was
`BASE.runtime_fingerprints()`; qualified 99b exposes `verify_runtime`, so the
fixed adapter uses its checked return value. The regression adapter deliberately
lacks the private function. No model request occurred. Real LTX-venv preflight
now verifies Torch 2.14.0+xpu, five runtime file bindings including both serializer
files, 15 source deltas and 31 added files, without materialization.

Final input-inventory SHA:
`9dde21a8295d94ab7c9911179f0c2bf8ea006eb4adbf33567f0fc1f514a852bc`.
Validation record: `data/resume-20261007/duration108-cpu-validation.json`.
Independent review found no blocker, including the adapter fix. Aggregate 4 GiB
usage remains checkpoint-observed filesystem deltas. Cache, preview and log
estimates are not separate hard quotas; raw captures have the explicit prewrite
shape/byte bound.

The fixed stopped-107b duplicate helper is prepared in
`recovery/20261007-post107b-retirement/`. Seventeen synthetic controls and an
independent review passed. It maps 40 archives directly to ten 105 native keepers,
excludes 36 protected anchors, and requires exact stopped identity, fresh complete
sealed proof, whole-file hashes/stats and durable restoration maps before deletion.
Helper SHA: `50570a90fa3ab460e013104ef045b9282a86a2fb581372b3840847e2d32d68da`.
No operational plan, cleanup or stop has been performed yet.
