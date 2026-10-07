# LTX upstream and exact context-transfer review — 2026-10-07

Read-only source audit after the owner resumed LTX optimization, requiring no
output degradation. No GPU, model, endpoint, Docker or systemd action was taken
for this review. No kernel or host setting was changed. This note proposes work;
it does not qualify a new runtime or change a sealed packet.

## Outcome and priorities

1. First reproduce the accepted batch-1 path with packet 98's 256×256 control.
   Preserve the progress-lock fix and disk admission in a successor runtime;
   do not patch historical packets in place. This is reliability work, with no
   claimed improvement to successful-clip speed.
2. A stage-owned, immutable conditioning buffer is a tractable *candidate* for
   avoiding repeated context copies. A downstream tensor-ID cache alone will
   not work reliably, and a stage-name cache alone is unsafe. The bounded design
   below avoids changing model arithmetic, but needs CPU ownership/mutation
   controls and a measured cost screen before substantial implementation.
3. After that screen, sampler scheduling is the next useful alternative:
   a batch-1 third worker with shared pools, or a narrowly justified two-card
   split rebalance. Do not repeat the old broad three/four-card placement matrix.
   Both alternatives need their own admission and exact-output gates. Neither
   has a predicted or measured win here.

New runtime development must start from the latest fetched upstream revision,
inventory/reapply the accepted overlay, and pass the existing `w93c` checks.
Packet 98 is a historical control, not the latest upstream qualification.

## Accepted measurement and unit boundary

The completed packet-97 batch-1 timed arm reports 1.3082 seconds per emitted
25-frame clip, or **19.11 generated frames per second**. Playback remains
24 frames per second: each clip contains 25/24 = 1.0417 seconds of video.
Reaching that sustained generation rate requires about 20.4% less time per
clip, not merely changing an output video's playback FPS. These are independent
clips, not demonstrated continuous scene generation or request latency.

The same receipt reports sampler job median 2.5301 seconds, mean 1.993 sampler
jobs in flight, and compute-engine seconds per clip of 1.2095 / 0.9634 / 0.8808 /
0.8440 on cards 0–3. Card 0 remains the busiest. These counters can include waits;
they are not a direct measurement of removable kernel work. Source:
[`summary.json`](../data/place-97/two-way-w2-b1-p1-dxpu2/summary.json), timed arm.

Batch 2 and batch 4 use different rounded outputs and their own reference sets.
Their 0.910/0.808-second long runs are not admissible substitutes under the
owner's current unchanged-output requirement. Larger packet-98 resolutions are
speed-only arms and do not close that quality requirement either.

## What is already done, and negative routes to avoid

- The short-window encoder is already the accepted reference. Lean conditioning
  already computes the connector once and reuses it three times per clip; the
  current receipt explicitly records 1 computed / 3 reused. The October 4 source
  survey's top two ideas must not be presented as new work.
- Shared graph pools and the second decoder on card 2 are already included.
  A third decoder and extra batch-2 workers did not improve packet 97.
- Packet 94's extra card boundaries lengthened the sampler chain; packet 95's
  three-worker spread layouts were exact but slower than its two-card control.
  Batch-1 two-card three-worker admission was then blocked by private-pool
  memory; shared pools subsequently changed that constraint. This leaves a
  narrow unmeasured screen, not justification for a topology sweep.
- Cross-step text **K/V** reuse remains invalid because timestep modulation
  changes those inputs. The proposal here only reuses exact transport of
  unmodified conditioning, not projected or modulated attention state.
- QKV fusion's old CPU-weight placement failure and small expected remaining
  benefit are preserved in [packet 85](graph-capture-85-results.md). Do not reopen
  it merely because a newer memory layout might fit the duplicate weights.

Relevant evidence: [packet 97](2026-10-06-packet-97-results.md),
[packet 94f](2026-10-04-packet-94f-results.md),
[packet 95 host-memory results](2026-10-04-host-ram-shadow-of-vram.md), and
[the existing progress-lock candidate](../recovery/20261007-progress-lock/README.md).

## Exact inspected source and upstream dependencies

Local Git source: `/home/steve/src/ComfyUI-ltx25-baseline`.
The checkout stayed at `19e1058f4c445ef74047e77a23f9ca7684c1e4b6`; the parent fetched
`b00c6e95279053474955540ba4f551646722b9aa` without changing that checkout.
This audit compared those commits with `git diff`/`git show` only.

Native files below are SHA-256 hashes of the exact Git blob bytes. Equal hashes
mean unchanged source, not qualification of the surrounding runtime.

| File | Old SHA-256 | New SHA-256 |
| --- | --- | --- |
| `comfy/conds.py` | `72058e9a22c972a9c875819e59d432d30d367fd2f7092ee6c6c45e5a60c959b0` | unchanged |
| `comfy/samplers.py` | `f2c264ca9d394612f828e3ffe167c856a278a10e1711b269f0ba65dccb66393f` | unchanged |
| `comfy/ldm/lightricks/av_model.py` | `6582ee5c9fe1119b0dfa85a7c5e4f6d94a899f3b551b1886546fd787c3799e7d` | unchanged |
| `comfy/model_base.py` | `6280712f8315f00f19a1ada53e48bf243c818b017fa751b3412092fa0f381e68` | `a1a1a7bb89a199710f996bf0bdf549d3e42484fe4dd91aa0a6361bb30c990508` |
| `comfy/ldm/lightricks/model.py` | `f0292be2a39491d411ad3cf4b58cebd87e62bf2568aafa35814b954828733718` | `e4bcd9361181c788cf207ae92c097fe3031dfcc63d80016e23b255b061ee11a0` |
| `comfy/ldm/modules/attention.py` | `9cafaafaf93ff53e8cbefb5e4a204014019985df2da8c1996bf40f1235fc2960` | `39d532217a60203c851697903b436ff1bef44d265846aedad1d0b0eda9d18ea0` |
| `comfy/ops.py` | `6058f688d936b083c49fa49a57964837476db6d95750ea70198ad60e884ffed0` | `da3c2aa00c5fa06f7d01322e159f43c8ec8171dc6f843446784c0acf6788cbe3` |
| `comfy/model_management.py` | `ef3f3af0657c1b022ad69b25928fa52dd429db9aed9cb688e89c7fbe68ab50cd` | `045ab96003386a43e647c8ab96f22fbf3be6c577e2fc578ea31c6faa22facbd5` |
| `comfy/text_encoders/gemma4.py` | `a0bec322e45e94e5c938c2b8bde0112d23805166a533612077915d594d18dbbc` | `6fc1b06e42e33bed5e69c208808551af839265ad319f4eb9a0aa40ecc62d179a` |
| `comfy/text_encoders/lt.py` | `3dafb59e756cd9d4c51614d7f476de92348ac2ef308c1249f8e1c6f76a12f871` | `5ef895ff2ade1ca4a5e5333e4e4141a332b45ebd6574d304ee76f10b36b0fcc0` |
| `comfy/ldm/lightricks/vae/audio_vae.py` | `f8a5818599859a93b8cb69240e4276fdc9e0eccc4c3e5fe64ca7608a480aa4c7` | `ba5a99f1573e12a9cff4b7ce0b3126afe374476d835ba3c04dc6a2e62ab3162c` |
| `comfy/ldm/lightricks/vocoders/vocoder.py` | `d2ff3ea7c40fc11705d1114d936afd1d466d36b05d95aa338f159ae14547494d` | `2030bc1b2ad541ae8a0f14b7a52d7383460b70685cb4bd81724915728b39bd08` |

No upstream replacement for the proposed context-transport mechanism was found.
However, the new `lightricks/model.py` changes CrossAttention dispatch to
`AttentionTensorContainer`/`ComfyAttention` and changes the feed-forward
activation call. Those are real attention/operator-overlay port dependencies,
alongside changed `attention.py`, `ops.py` and `model_management.py`. Do not
refresh their hashes without reviewing behavior and rerunning exact gates.
The changed `model_base.py` hunks inspected are other model families; LTX's
`extra_conds` path itself is unchanged. Gemma/lt changes include audio, template,
generation interfaces and dynamic-residency discovery. Audio VAE preprocessing
now uses `comfy.audio` instead of torchaudio. The vocoder change is commentary.
This is a bounded dependency review, not a complete accepted-overlay port.

Transport/ownership source was read from the sealed packet-98 tree:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98/source`.

| Relative file | SHA-256 | Inspected mechanism |
| --- | --- | --- |
| `scripts/ltx_graph_capture.py` | `3a9a99954cb4877829c4407eb74306f6b409864002dfcccf3562fd0c98380400` | `Slot` at 342; `fill` at 455; `staged_move` at 822; routing at 1263; `_staged_cached` at 1292 |
| `scripts/ltx_layer_shard.py` | `9caaec0aeb68e9f391fab5ae9b6a63e464aa62a99e1ffc449775b3687d2149b2` | 23/25 placement at 24–34; per-forward cache lifetime at 117–130 |
| `scripts/ltx_lean_conditioning.py` | `6740d6665c7dea622fc859287cf075bc01a5e521a7154e6138afaf6afbad7d99` | begin/stage/end at 72–120; per-clip connector memo at 122–143 |
| `scripts/pipeline_sampler_node.py` | `1d20b4ad3341710f71a36d8d1bef57e0f11004a4a9cb5bbd46bced1407e377b0` | clip ownership/final cleanup at 520–568; stage changes at 619/629 |

## Minimal candidate and the ownership trap

`comfy/conds.py:44–48` always calls `torch.cat`, including a singleton. Its
`process_cond` at 33–34 creates another condition wrapper; the batch-size-one
case of `comfy/utils.py:895–900` returns the same underlying tensor. Native
`samplers.py:148–163` then concatenates the wrappers on every forward.
`av_model.py:851–871` splits and views that context into video/audio views;
with `caption_proj_before_connector=True`, `model.py:887–894` only views it.
Consequently fresh tensor/storage identities can occur despite unchanged bytes.

A tractable scoped route is a stage-owned `CONDRegular` specialization, installed
only for this batch-1 LTX `c_crossattn` path:

1. Create a unique owner object when the stage's real connector result is made.
   It belongs to the sampler worker thread and clip instance, not a prompt string,
   fixture ID, tensor address alone or process-global cache. Stage b gets another
   owner even when its bytes equal stage a.
2. Preserve the original singleton `torch.cat` once to make an owned contiguous
   tensor with the native output layout. Subsequent singleton concatenations may
   return that owner's tensor only through checked child wrappers. Do not replace
   all `CONDRegular.concat` calls globally or return an arbitrary input alias.
3. Carry the owner through `process_cond` only when batch, source identity,
   dtype, device and shape still satisfy the exact singleton path. Nonempty
   concatenation, repeat/narrow, masks, hooks, alternate conditioning, CFG changes,
   foreign ownership or changed source contract refuse the optimized route.
4. Recognize the block's video/audio context only as exact bounded views of that
   owner: storage identity, offset, shape, stride, dtype and device must match.
   Cache only its staged destination copies, keyed by owner, context role and
   destination. All timestep, positional, activation and K/V arguments retain
   existing behavior. Keep normal per-forward transport as the explicit baseline.
5. Retain ownership references until stage/clip cleanup; clear in `finally` after
   existing stream completion. Never reuse across workers, stages, clips or
   allocation-address recycling. Count copies, skipped copies and refusal reasons.

**Mutation is the key unresolved contract.** Returning an existing tensor changes
aliasing compared with `cat` on every call. Before implementing reuse, prove the
pinned selected path never mutates these owned inputs. A normal version-tracked
owned tensor can catch ordinary in-place writes, but inference tensors may have
no version counter, and graph/device writes need not bump it. Do not treat
`_version` alone as proof. The native block applies timestep modulation to a new
context result, but the complete cast/view/hook path and graph static ownership
must be checked. Unsupported mutation tracking must refuse or use the original
path, not silently accept. End-stage/context sentries and full output comparison
remain required even after the structural argument.

The simplest correctness diagnostic instead byte-compares each live context with
a retained first-context clone before reusing a staged copy. That handles fresh
singleton-cat tensors, signed zero and changed values, but introduces device
synchronization and may erase the gain. It is a diagnostic control, not a reason
to add a larger cache framework.

## Size the gain before building the optimization

At batch 1 the transported context is 1024 × (4096 + 2048) × 2 bytes = **12 MiB**
per forward. Eleven forwards versus one transport for each of two stages removes
at most **108 MiB per transfer leg per clip**, plus the corresponding repeated
destination static fills, for this one secondary sampler card. The current mover
waits on a host event for each tensor, so eliminating 18 context-copy waits is
also plausible. This is byte/count arithmetic, **not a measured latency saving**.
It excludes activations, timestep work and the transformer's large weight reads.

The raw byte saving is modest relative to a 1.3082-second clip. It is unlikely to
deliver the required 20.4% alone; costly synchronization would have to dominate
for it to become a large lever. During the admitted control, inspect existing
phase evidence first. Only if context transport is material should a narrow
copy-count/timing screen follow. If it is a percent-or-two item, close this lever
quickly and move to sampler scheduling/operator work rather than building a
general provenance system around it.

CPU controls before any candidate GPU use must cover actual singleton native
output bytes/layout; signed zero/nonfinite bit patterns; stage and thread
isolation; alias/in-place mutation; source replacement/address reuse; unexpected
concat/batch/mask rejection; inference-mode version limitations; exception
cleanup; and unchanged fallback calls. These tests have **not** been written or
run in this audit. CPU controls do not establish model output parity or speed.

Any live successor then needs source/overlay admission, unchanged arithmetic and
sampling policy, eager/capture replay checks, all ten accepted `w93c` fixtures,
per-clip context and emitted-index checks, complete sustained timing including
tail gaps, and the existing fault-halt/graceful-stop rules. No new endpoint call
is authorized by this note itself; the parent owns the resumed experiment plan.

## Follow-up: complete source census and packet-99 transplant

The bounded census subsequently compared SHA-256 of all 1,191 frozen upstream
Git blobs against packet 98's manifest. Its 1,254 source files contain all 1,191
upstream files plus 63 lab additions. Exactly five native files differ:
`comfy/model_patcher.py`, `comfy/sd.py`, `comfy/sd1_clip.py`,
`comfy/text_encoders/lt.py`, and `comfy/ldm/lightricks/av_model.py`.
There are no omitted old-upstream files and no collisions between the 63 lab
additions and the new upstream tree. New upstream adds 81 files and removes
`comfy_api_nodes/nodes_sora.py` and
`tests-unit/comfy_test/seedvr_vae_forward_test.py`. Preserve these deletions in
the new live source tree; their historical identity remains in packet 98.

Four native overlays merge cleanly using actual `git merge-file -p` with
process-local memfd inputs and no checkout/build writes. The sole textual
conflict is `comfy/sd.py`: latest upstream adds
`fast_disk=comfy.storage.state_dict_fast_disk(state_dict)` to the CLIP
ModelPatcher constructor, while the overlay inserts the small-state option guard
and propagation immediately after that constructor. The explicit resolution is
the **new constructor followed by the unchanged overlay guard/propagation**.
Clean textual merging does not prove semantic compatibility: the new
ModelPatcher fast-disk constructor/clone behavior, attention dispatch and
residency changes still need their source contracts and CPU gates reviewed.

Source-only output would have 1,333 files: 1,270 new upstream plus 63 additions,
with five native overlay merges replacing their upstream versions. The remaining
247 files of packet 98's 1,501-file closure are graphs, launchers, patches,
provenance and parent manifests. They remain explicitly historical dependencies;
a source-only preparation must not claim to preserve their current launchability.
Its transition inventory must account for every old path, including native
upstream updates and removals. Do not copy 1,254 old source files over a new
archive, which would silently restore obsolete upstream files and code.

The old checker (`launch/encoder_runtime_common.py:261,295–298,397–410`) pins
the old commit, requires parent/runtime identity equality, requires inherited
file equality and enforces an exact parent-plus-additions inventory. A new
transition-aware checker is necessary; changing `PIN` or refreshing all hashes
would erase the meaning of those checks. Preserve old manifests byte-for-byte
as history, validate the new source against its actual Git tree plus declared
overlay transformations, and retain the existing model, graph, mirror,
source-tripwire, admission and runtime-identity checks under a new schema.

The parent selected a possible later **20/28** sampler split, after a distinct
new-base control. The source transplant must retain **23/25**, so upstream
refresh and topology changes cannot be conflated. No new-base source tree or
model execution was created by the in-memory census/merge review.

### Source-only preparer readiness

[`prepare-upstream-99.py`](../scripts/prepare-upstream-99.py) now implements this
bounded transplant. Default `--plan` reads Git objects and the named small packet
files, verifies the fixed census and produces a complete source/old-file
disposition JSON without creating a source tree. `--prepare --out ABSOLUTE_NEW_PATH`
is a separate, explicit action; it has **not been run**. It requires a new path
outside the historical packet and checkout, and a 50 GiB free-space reserve plus
384 MiB allowance. It exports the actual new Git archive, verifies every archive
member against the Git tree (including omitted/substituted export detection),
applies only the five reviewed native transformations, retains all 63 lab
additions and writes `UNSEALED-NOT-LAUNCHABLE`. Final source size is planned at
49,785,325 bytes. It provides no launcher or runtime checker.

Repeatable read-only controls:

```bash
python3 -B experiments/ltx25-b70/scripts/prepare-upstream-99.py --self-test
python3 -B experiments/ltx25-b70/scripts/prepare-upstream-99.py --plan
```

All five self-test controls passed: independent edits merge with exact expected
bytes; unknown conflicts refuse, including an unexpected conflict in `sd.py`;
an incorrect historical manifest digest refuses; the actual pinned source plan
covers all 1,501 historical paths and recognizes the sole permitted conflict.
An additional CLI refusal check confirmed `--plan --out ...` cannot prepare a
directory. These controls do not exercise materialization, dependency imports,
GPU behavior, runtime sealing or the eventual new-base quality gate.
