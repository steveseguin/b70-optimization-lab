# LTX 2.5 native BF16 baseline on B70

Status: **1.607 s per distinct clip, bytewise exact on ten fixtures, September 17, 2026**
(packet 74: two clips in flight across the two shard cards, on top of the
graph-captured pipeline with the resident fast path and save-behind). That
is 1.54 s of wall per second of video, about 15.6 fps equivalent; the goal
is 1.00 s (24 fps) and it is not met. The stream now sits on the text
encoder's ceiling (one 1.59 s fp32 encode per clip on one card), so the
next lever is the encoder two prompts deep across two cards. History: the
[September 16 audit](notes/2026-09-16-audit-of-sep15-16-claims.md), then
packets [58](notes/graph-capture-58-results.md), [64](notes/graph-capture-64-results.md),
[65](notes/graph-capture-65-results.md), [72](notes/graph-capture-72-results.md)
[74](notes/graph-capture-74-results.md) and [82](notes/graph-capture-82-results.md)
(sharded encoder: exact but for one race clip, no gain, the sampler now paces).

Direction: [north star, milestones and next work](PLAN.md).
The actual goal is one second of new video in under one second at 24 fps,
with final output at least 256x256 and no quality loss. Continuous recording
is unnecessary; keep a small review set and exact verification receipts.
The measured lossless ceiling on this hardware is recorded in
[what 24 fps requires](notes/what-24fps-requires.md): total per-clip work
(sampler 2.02 s on two cards, text encode 1.59 s, decode 0.74 s) divided over
four cards is 1.09 s at perfect balance, against a 1.042 s budget, so 24 fps
needs both a full pipeline re-architecture and a real reduction of the
sampler's own time. Earlier campaign history (first 30-request campaign,
6.44-7.10 s split placement) remains below as the preserved reference.

The [first 30-request campaign](notes/stability-01-results.md) passed all ten
fixture repeats at 6.515 s median preview. It reclaimed 607 MB of verified
temporary output and kept only three small campaign previews.

## Current optimized baseline

The selected experimental setup uses all four 32 GiB B70s. The original BF16
transformer is split across two GPUs; the other cards encode text and decode
video/audio. A 256x256, 25-frame clip at 24 fps reaches playable preview in
6.44–7.10 seconds after loading. Three boat generations and two other scenes
match their original references byte-for-byte across all four saved tensors.
Warm boat client completion improved **7.85×** against the original single-card
baseline, using matched timing definitions. Text, sampling and decoding are
recomputed each time; only loaded model components are retained.

The first split placement request took 81.21 seconds to preview, including
initialization. The transformer is fully resident but the encoder still
partially offloads to CPU. The clip lasts about one second, so continuous
real-time generation and prolonged operation remain unqualified. Resolution,
frame count, sampler steps and precision are unchanged. Exactness is scoped to
the tested native distilled checkpoint and fixtures, not another model/runtime.

See the [speed results and limitations](SPEED-HANDOFF.md) and
[structured measurements](data/speed-resident/summary.json).
The selected split run's exact media passed an independent decode check:
[lossless verification](data/speed-resident/float-lossless.verification.json).
Its files are under `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`:

- `output/resident-split-03/preview_00001_.mp4`: convenient lossy preview.
- `output/resident-split-03/float-lossless.mkv`: exact float video/audio;
  experimental FFV1 float profile, exported separately from the latency timer.
- `output/validation/resident-split-03/tensors.safetensors`: all four raw outputs.

## Original single-card baseline (preserved reference)

LTX 2.5 distilled BF16 generated a 256x256, 25-frame clip at 24 fps on one B70
with synchronous CPU weight offload. First/middle/last frames show a wooden boat
moving gently on water. All three runs fully recomputed the same prompt and seed;
decoded images, video latents, audio latents and waveform are bitwise identical,
with zero unequal values and zero maximum difference. Strict deterministic
algorithms remained enabled with warning-only mode off. No GPU fault, OOM or
tiled-VAE fallback was recorded. This original process was later replaced once
by the current speed server, after a planned graceful shutdown.

| Run | Server execution | Client elapsed | Cached nodes |
| --- | ---: | ---: | ---: |
| First | 97.590 s | 100.943 s | 0 |
| Repeat 1 | 54.009 s | 55.431 s | 0 |
| Repeat 2 | 52.774 s | 55.021 s | 0 |

The native weights are BF16; upstream latents and decoded outputs are FP32.
The exact tensor archive and FFV1 v4 float RGB32/PCM float32 media retain those
outputs without quantization. Decoding the media independently reproduced every
video/audio byte, including 24 fps and 48 kHz sample rate. FFV1's float profile is
experimental; the MP4 is the convenient lossy preview. PNG previews also convert
the original float pixels to 8-bit values. The video lasts 25/24 seconds; original
audio is 48,480 samples (1.010 seconds), preserved without padding or resampling.

Original baseline scope: **one prompt/seed, one process, one hardware/software configuration**.
No fresh-process, different-seed/resolution, CUDA, dev-checkpoint or FP32-model
parity claim is made. Distillation itself is not claimed lossless.

Evidence: [result identity](data/baseline-result.json),
[independent repeat verification](data/repeat-verification.json),
[lossless round-trip receipt](data/float-lossless.verification.json),
[server log](data/server-baseline-complete.log), and
[post-run kernel journal](data/journal-after-baseline.txt).
Submitted graphs, server histories, identities and capture summaries are under
`data/requests/baseline-01`, `baseline-02` and `baseline-03`.

Media under `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`:

- `output/baseline-01/preview_00001_.mp4`: viewable preview.
- `output/baseline-01/float-lossless.mkv`: exact float video and audio.
- `output/validation/baseline-01/tensors.safetensors`: canonical four-output archive.

## Reuse the current server

The current endpoint is `http://127.0.0.1:8188`, PID 24848. Do not start a second
server or cycle this one to run another clip. Confirm the queue is idle and the
fault latch is absent; the client enforces those conditions. Use a new output
identifier, since evidence directories are never overwritten:

```bash
cd /home/steve/llm-optimizations
/home/steve/.venvs/ltx25-baseline/bin/python experiments/ltx25-b70/scripts/profile-clip.py resident-split-next \
  --graph experiments/ltx25-b70/data/speed-resident-split-api.json \
  --server-run /mnt/fast-ai/bench-results/ltx25-baseline-20260913/speed-server
```

Use a new run name each time. Keep node420 placement `split`; switching it
reconstructs components and invalidates a warm-latency comparison. The original
`request-clip.py` binds the old server identity and is a historical baseline
client, not the current reuse command. Compare new split runs against the frozen
baseline with `scripts/compare-clip.py baseline-01 NEW_RUN --output NEW_RECEIPT`.
For same-graph repeats use `scripts/verify-repeats.py` with at least three unique
run names and a fresh `--output` receipt. Export another exact media file
with `scripts/export-lossless.py SOURCE_VALIDATION_DIRECTORY NEW_MKV_PATH`.
Runtime versions are pinned in [environment capture](data/environment.txt);
current startup flags and host/source identity are in
[server arguments](data/speed-resident/server-args.json) and
[server identity](data/speed-resident/server-identity.json). ComfyUI core is
unmodified. The capture extension saves outputs and gates requests; the speed
extension retains components and routes original transformer blocks between GPUs.
Loaded extension hashes are recorded in the server identity. Original startup
receipts remain under `data/server-args.json` and `data/server-identity.json`.

## Preregistered baseline

- Checkpoint: official distilled BF16 LTX 2.5, revision
  `5e6e71018ee1756ed329b697a7b4aedc934dfce9`. This is its own target;
  distillation is not claimed lossless relative to the distinct dev model.
- Native BF16 transformer and custom Gemma4 encoder; no additional quantization,
  LoRA, approximation, compilation or attention shortcut. Preserve upstream
  component precision and explicitly record any compute upcasting.
- Official two-stage text-to-video workflow: 256x256, 25 frames at 24 fps,
  8-step first stage and 3-step refinement; fixed seed 42 in both noise nodes.
- One XPU with synchronous CPU offload, including the text encoder. One
  continuously running local server, sequential requests, no restart chains.
- Save uncompressed generated tensors, lossless PNG frames, audio waveform,
  and a viewable video. Compare tensor hashes, finiteness and exact values
  across at least three actual recomputations with node-result caching disabled.
  Record first versus repeat timings separately. Lossless media encoding does
  not establish model quality or bitwise numerical determinism by itself.
- Fail closed on reported nondeterministic operations initially. If unsupported,
  preserve the failure and qualify any revised numerical identity explicitly.
- Faults halt new requests. No power, swap, page-cache, driver or reboot changes.
  Fresh-process repeatability is deferred under the no-restart constraint.

## Sources and storage

ComfyUI source: `19e1058f4c445ef74047e77a23f9ca7684c1e4b6`, upstream snapshot at
`/home/steve/src/ComfyUI-ltx25-baseline`. Exact environment will be frozen after
installation. Official workflow snapshot is in `data/upstream-t2v-workflow.json`;
source URL: https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_ltx2_5_t2v.json.

The selected five component files are copied sequentially from the read-only
RAID to `/mnt/fast-ai/llm-models/LTX-2.5-baseline`, with source and destination
SHA-256 matched to the original intake manifest. Model bytes stay outside Git.
Full evidence and media: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.
The Qwen archive remains separately blocked on Corsair mount/verification;
its local weights and all prior research artifacts are preserved.

Before first execution, source review changed the encoder placement from CPU
to the default XPU path and removed `--lowvram`: this CPU lacks native BF16
matrix instructions. ComfyUI's normal memory mode retains partial-weight
offloading, with 6 GiB reserved. No CPU-encoder measurement was made.

## Input integrity failure before first generation

The September 12 RAID copy of the distilled transformer failed its fresh
staging hash. The copied file hashes to
`ad9eb77d12e611917f91cc71df924c6383a30cbf306b4d4afdf990912af0ebe9`;
authenticated publisher metadata at the pinned revision confirms the expected
`31eb3cad89b9e54e99dd3baf286f70825ac4f6c660a70d9184d895be76d7bff4`.
Size and first MiB match; a zero-page screen found no entirely zero 4 KiB pages.
No inference used these bytes. The original RAID is unchanged; the rejected
internal copy is preserved in the evidence root's `quarantine/` directory.

The original download helper reported a successful hash but did not explicitly
fsync files and trusts old verified statuses plus size on resume. That does not
establish the timing or cause of the present corruption. It is not a GPU result.

`scripts/download-verified.py` fetches a replacement at the same pinned revision,
checks network SHA-256, fsyncs the file, checks persisted bytes via O_DIRECT,
then renames and fsyncs the parent directory. It makes one attempt, with no
automatic retry or server restart. Other selected components are being checked
separately. The initial failed receipt and log remain preserved; the server
gate stays closed until the complete component set is verified.

The repair localized 79 changed bytes in one 8 MiB region starting at byte
310,378,496. Replacing that region in a separate copy restored the full
publisher SHA-256; an O_DIRECT reread also passed. The exact reversible delta
is preserved in `data/transformer-corruption-byte-delta.json` and the proof in
`data/localized-repair-promotion.json`. The original rejected file, old/new
region bytes and partial publisher download remain outside Git in the evidence
root. The now-redundant download was stopped once, after verification succeeded;
the ComfyUI server was not stopped or restarted.

The encoder also failed staging: expected
`ef7243612fdae7a75cb4d5cee9433e81380675fb6c213bd98ae74a9cd16561d1`,
observed `24ab21fc0b5c3613f6f079393146c28a3ba68b0ec5886eeb671c437ec6d2e5e4`.
The full rejected copy and failed receipt remain in the evidence root. A pinned
replacement download is compared blockwise by `scripts/locate-encoder-damage.py`;
`scripts/repair-encoder-candidate.py` can make one separate candidate from a
localized difference cluster. It publishes only after full-file publisher and
persisted direct-I/O hashes pass. The finalizer independently hashes all five
final files and preserves original staging failures before opening the gate.

Pre-execution review strengthened the client and repeat verifier to bind each
actual server history to its submitted graph, unique prompt ID, server process,
boot and model-verification receipt. All four tensor outputs and audio sample
rate must match. The float-media exporter reads only needed tensors so BF16
latents do not require unsupported NumPy BF16 conversion.

Encoder repair succeeded: 112 changed bytes in the 8 MiB block starting at
10,158,604,288 were replaced in a separate candidate. The full publisher hash
and direct-I/O reread both matched; `data/encoder-repair-promotion.json` retains
every changed byte and the verification receipt. Its redundant network download
was stopped once after successful promotion, preserving the 11.17 GB publisher
prefix. The server remained running and had still received no generation.
