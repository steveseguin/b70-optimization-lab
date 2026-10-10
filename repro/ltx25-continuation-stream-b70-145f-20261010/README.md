# LTX 2.5 continuation video on four Intel Arc Pro B70s

**Lab replay; public installer incomplete.** This guide preserves the measured
145-frame setup, its commands, source recovery path and output checks. It does
not yet let a fresh host obtain the entire sealed runtime from public downloads.
The missing inputs are listed below and in [publication status](publication-status.json).

The measured packet 135 setup generated six seconds of new 256×256 video in
**5.2415 seconds median** during each of two 52-period early, unthrottled windows.
That is about **0.874 seconds of work per second of new video**. The older
**5.248 seconds / 0.875 s/s** value is the GC60 session's raw delivery cadence,
including client pacing. Neither is a sustained unthrottled throughput promise.
All values and source intervals are in the [frozen evidence](evidence/pacing-snapshot.json).

Packet 137 adds a bulk F32 finiteness scan to that setup. Its saved startup
identity and CPU build evidence are available, but this snapshot contains no
native qualification verdict or measured streaming rate for 137. The production
configuration file selecting it is not itself a quality or speed receipt.

## Choose the result you want to reproduce

| Profile | Settings beyond the shared setup | What is established |
| --- | --- | --- |
| Packet 135 GC60 | 60-second cleanup cadence; parent F32 scan | 121 completed chunks; native eager/graph/repeat gate; 52 early unthrottled periods |
| Packet 135 GC10 | 10-second cleanup cadence; parent F32 scan | 757 completed chunks; native eager/graph/repeat gate; 52 early unthrottled periods |
| Packet 137 bulk | 10-second cleanup cadence; bulk F32 scan | CPU tests and sealed/startup identities; native verdict and rate absent from this snapshot |

The shared setup is four B70s, native distilled BF16, frame-anchored continuation,
145 frames at 24 fps, 256×256 final images, two-stage sampling with the original
8+3 steps, cone anchor decoding under the decoder graph, full eager display on
`xpu:3`, idle maintenance, signature-digest caching and background storage scans.
Sampling is one sequential queue, one worker, batch one, shared pool, with blocks
0–19 and 20–47 split across cards 0 and 1. Text `split36` means layers 0–35 on
card 2 and 36–47 on card 3. Audio and other auxiliaries retain legacy placement.

One anchored frame overlaps the previous chunk: `(145−1)/24 = 6` new seconds.
The sink drops that repeated first frame. Playback at 24 fps and optional 768×768
sink scaling are not native generation resolution or model throughput.

## Identity and prerequisites

[identity.json](identity.json) pins both sealed manifests and inner-plan hashes.
The native packet 135 [server identity](evidence/135-gc60-server-identity.json)
and [health receipt](evidence/135-gc60-health.json) record:

| Component | Measured identity |
| --- | --- |
| Target | `Lightricks/LTX-2.5`, distilled 22B BF16; revision `5e6e71018ee1756ed329b697a7b4aedc934dfce9` |
| Runtime source | ComfyUI `b00c6e95279053474955540ba4f551646722b9aa`, plus the sealed lab overlay |
| Python | 3.12.13; runtime fingerprints require the venv executable `bin/python`, not its `bin/python3` alias |
| PyTorch | `2.14.0+xpu` |
| Host kernel | `7.0.0-39-generic` |
| Reported Intel driver | `1.15.38308+1`, Unified Runtime over Level Zero V2 |
| Cards | four Arc Pro B70s; each reported 32,656 MB total memory |
| Platform inventory | [Observed Python packages](../../experiments/ltx25-b70/data/environment.txt): Triton XPU 3.8.0, Intel compiler/SYCL runtimes 2026.1.0, PyAV 18.1.0 |

The package list is an observed inventory, not an installable wheel lock.
No immutable installer set for the exact driver, Python and XPU wheels has been
published with this recipe. Installing today's similarly named packages does
not establish this runtime identity. The historical native venv is
`/home/steve/.venvs/ltx25-baseline`; its interpreter and selected library byte
hashes are in the saved identity. There is no certified Docker image/digest for
this LTX recipe.

Use an otherwise idle four-card Linux host with enough host RAM and disk for
all components, compiled state, captures and the reserve below. The originating
machine has 128 GiB installed RAM; a smaller host-memory minimum has not been
qualified. Do not copy the originating host's memory exclusions or power
workarounds onto another machine.

## Obtain and verify model files

The [model verification receipt](../../experiments/ltx25-b70/data/model-verification.json)
contains every filename, exact byte size and full SHA256 for these five inputs:

| Component | File | Bytes | SHA256 |
| --- | --- | ---: | --- |
| Transformer | `diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors` | 42018190584 | `31eb3cad89b9e54e99dd3baf286f70825ac4f6c660a70d9184d895be76d7bff4` |
| Upscaler | `latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | 995778752 | `eb5a71fe4068ee87ccdb1c3aa635e547ca76bd2d30ae20ae889f2c325c0677e8` |
| Audio VAE | `vae/ltx-2.5-audio-vae-bf16.safetensors` | 364866540 | `c52733d37f6a7fb7949c3dc0fb468c6cb2169e4d836983a73babb9f0d54837a5` |
| Video VAE | `vae/ltx-2.5-video-vae-bf16.safetensors` | 1472223346 | `847e14ca7f3355debca0cea4eaa24ac0fbcdf0061da054ac89ca638a869ddba3` |
| Text encoder | `text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors` | 26263858182 | `ef7243612fdae7a75cb4d5cee9433e81380675fb6c213bd98ae74a9cd16561d1` |

Download each path from the publisher at that exact revision, honoring its
license/access terms. For an already installed Hugging Face CLI, from the repo
root, this preparatory command obtains only the declared model inputs:

```bash
export LTX_MODEL_DIR="$HOME/ltx25-model"
hf download Lightricks/LTX-2.5 --revision 5e6e71018ee1756ed329b697a7b4aedc934dfce9 \
  --include 'diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors' \
  'latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors' \
  'vae/ltx-2.5-audio-vae-bf16.safetensors' 'vae/ltx-2.5-video-vae-bf16.safetensors' \
  'text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors' \
  --local-dir "$LTX_MODEL_DIR"
nice -n 19 env OMP_NUM_THREADS=2 python3 -B - <<'PY'
import hashlib, json, os
from pathlib import Path
root = Path(os.environ['LTX_MODEL_DIR'])
receipt = json.loads(Path('experiments/ltx25-b70/data/model-verification.json').read_text())
lines = []
for item in receipt['files']:
    p = root / item['name']
    assert p.stat().st_size == item['bytes'], p
    with p.open('rb') as f:
        actual = hashlib.file_digest(f, 'sha256').hexdigest()
    assert actual == item['sha256'], p
    lines.append(actual + '  ' + item['name'])
    p.chmod(0o444)
with (root / 'DOWNLOAD-MANIFEST.txt').open('x') as f:
    f.write('\n'.join(lines) + '\n')
PY
```

This does not install or launch the model. The original receipt also records
successful direct-I/O verification; the ordinary read above is only the first
verification step. A new host needs its own model-verification receipt bound to
its actual paths. Never substitute an FP8 checkpoint, a dev checkpoint, a LoRA,
fewer sampling steps or a lower-resolution output and call it this result.

## Restore the sealed source packet

The in-repository recovery trees contain reviewed components, launchers,
contracts, reference hashes and CPU tests:
[packet 135](../../experiments/ltx25-b70/recovery/20261010-continuation135-stream/LAUNCH.md),
[packet 137](../../experiments/ltx25-b70/recovery/20261010-continuation137-stream/LAUNCH.md).
The exact incremental builders are
[135 runtime_packet.py](../../experiments/ltx25-b70/recovery/20261010-continuation135-stream/runtime_packet.py)
and [137 runtime_packet.py](../../experiments/ltx25-b70/recovery/20261010-continuation137-stream/runtime_packet.py).

These builders are **not standalone clean-host builders**. Packet 137 imports
its sealed 135 parent while loading, 135 requires sealed 133b, and inherited
helpers require earlier prepared packets including 111. They also pin the
originating repository, model and venv locations. The recursive verification in
the build receipts proves the local assembled source chain; it does not prove
public availability of that chain. No sealed-packet archive URL is published
in this guide. Do not create empty parent folders or weaken a hash check.

On a reconstruction host where the complete pinned parent chain is already
restored, these are the exact incremental build commands (not executed by this
publication task):

```bash
PY=/home/steve/.venvs/ltx25-baseline/bin/python
nice -n 19 env OMP_NUM_THREADS=2 "$PY" -B \
  experiments/ltx25-b70/recovery/20261010-continuation135-stream/runtime_packet.py \
  --build --input-inventory-sha256 2f39540fc2c08ebfa9061aee7b9603dac40dd44bea70cf7352e930b28fb1f859
nice -n 19 env OMP_NUM_THREADS=2 "$PY" -B \
  experiments/ltx25-b70/recovery/20261010-continuation137-stream/runtime_packet.py \
  --build --input-inventory-sha256 8758abc7adca4ad6e556890dd3f3fe5919b4668d7d5a675a160e911f9566e696
```

Builders refuse collisions: preserve any existing sealed packet. Validate using
`--verify-manifest-sha256` instead of `--build` when verifying an existing packet.
The expected manifests are `4356482eae2f1d7ac95b17e6483379ceed0cc90ed488d46765803451980402c3`
for 135 and `18c80d25c2ba4992d8c6dff24779737a056a325389a84486d24da674ef7e463e`
for 137. The client pins the **inner plan** (`identity.json`), not the plan file's
outer byte hash. CPU build gates and counts are recorded in the
[135 receipt](../../experiments/ltx25-b70/data/resume-20261008/continuation135-build.json)
and [137 receipt](../../experiments/ltx25-b70/data/resume-20261008/continuation137-build.json).

Before calling this publicly reproducible, publish the entire parent source
chain and exact runtime inputs, make the paths portable without weakening the
seals, rebuild from a pristine public commit, run native qualification on a
supported fresh host, then publish real release assets and a
`neural.download.recipe-publication.v2` manifest. Run both local and
`--check-remote` modes of `tools/validate-recipe-publication.py`. The missing
`publication-manifest.json` is an explicit incomplete-publication gate; this
recipe's `publication-status.json` is not a substitute certificate.

## Launch and health: qualified reconstruction hosts only

The following commands are recorded operating instructions, not permission to
use a shared live machine. They assume the pinned venv, restored packet and
model paths, clean output namespace and exclusive ownership of the four cards.
Check the host's current owner instructions first. Keep the owner floors:
**at least 256×256 final output and no quality/losslessness sacrifice**; the
performance target is below one work-second per new video-second.

Obtain a new health receipt with the
[one-shot four-card probe](../../experiments/ltx25-b70/scripts/check-four-card-health.py)
only when GPU work is authorized and the cards are empty:

```bash
PY=/home/steve/.venvs/ltx25-baseline/bin/python
"$PY" -B experiments/ltx25-b70/scripts/check-four-card-health.py \
  /absolute/new/evidence-directory/health.json
```

A receipt from this guide is historical evidence, never current admission.
Packet 135 GC60, the clean 121-chunk measured profile:

```bash
env -u LTX_DISPLAY_REPLICA_TRANSIENT_GIB \
  LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=text-shift \
  LTX_AUDIO_RESIDENCY=legacy LTX_CONE_CAPTURE_RESERVE=parent \
  LTX_DISPLAY_ALLOCATOR_RELEASE=off LTX_AUX_RESIDENCY=legacy \
  LTX_DISPLAY_WORKER=serial LTX_MAINTENANCE_MODE=idle \
  LTX_GC_INTERVAL_SECONDS=60 LTX_SNAPSHOT_DIGEST_CACHE=1 \
  LTX_STORAGE_SCAN_MODE=background LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
  experiments/ltx25-b70/recovery/20261010-continuation135-stream/launch-135.sh \
  145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:3 \
  /absolute/new/evidence-directory/health.json
```

For packet 135 GC10, change only `LTX_GC_INTERVAL_SECONDS=10` and use a new
identity/work directory. For packet 137, use the
[exact launch/client pair](../../experiments/ltx25-b70/recovery/20261010-continuation137-stream/LAUNCH.md)
with GC10 and `LTX_F32_SCAN=bulk`. The client requires the distinct variable
`LTX_EXPECT_F32_SCAN=bulk`. Do not claim a measured benefit for that switch.
The [recorded production arm](../../experiments/ltx25-b70/stream/ops/production-arm.json)
shows all settings together; it is mutable operational metadata, not a receipt.

Launchers enforce `EnableDeferBacking=0`, `NEOReadDebugKeys=1`, OMP/MKL threads
2, output size, one sampler worker and the exact source/manifest contract. They
start one systemd user unit with `Restart=no`, SIGINT and `SendSIGKILL=no`.
They refuse busy ports, old run names, fault latches and changed runtime bytes;
do not bypass a refusal or automatically retry a failed launch.

## Client, local viewing, relay and graceful stop

The server command's `env` settings do not persist in the calling shell.
Repeat them explicitly when starting
[start-client-135.sh](../../experiments/ltx25-b70/stream/start-client-135.sh)
for the measured GC60 profile, using a new private work directory:

```bash
env -u LTX_DISPLAY_REPLICA_TRANSIENT_GIB \
  LTX_STREAM_WORKDIR=/absolute/new/stream-work \
  LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=text-shift \
  LTX_AUDIO_RESIDENCY=legacy LTX_CONE_CAPTURE_RESERVE=parent \
  LTX_DISPLAY_ALLOCATOR_RELEASE=off LTX_AUX_RESIDENCY=legacy \
  LTX_DISPLAY_WORKER=serial LTX_MAINTENANCE_MODE=idle \
  LTX_GC_INTERVAL_SECONDS=60 LTX_SNAPSHOT_DIGEST_CACHE=1 \
  LTX_STORAGE_SCAN_MODE=background LTX_RUN_WRITE_ALLOWANCE_GIB=16 \
  experiments/ltx25-b70/stream/start-client-135.sh \
  145 1 cone 1 1 fingerprint none eager-display 0 full xpu:3
```

**This wrapper enables deletion of consumed previews.** It passes
`--delete-consumed-previews` unconditionally. The client reads the sink's
`last_played_seq`; with the default `--dispose-margin 50`, it may unlink a tracked
preview only when its manifest sequence is at least 50 behind that acknowledgement.
It accepts only the packet's stream-directory/preview-filename pattern directly
under the output directory and rejects symlink files/directories. It removes the
parent directory only if empty. This disposal path does not delete receipts,
qualification captures, anchors, logs or manifests, and does nothing without a
readable sink acknowledgement. There is no wrapper flag to negate the boolean;
a retention-preserving deployment needs a reviewed copy without that option or
a direct client invocation, with disk admission still enforced. Do not run this
wrapper against evidence whose preview retention is required.

For the GC10 profile, change the client and server cleanup cadence together to
10. Packet 137 uses
[start-client-137.sh](../../experiments/ltx25-b70/stream/start-client-137.sh)
and the extra expected F32 mode above. The
[client](../../experiments/ltx25-b70/stream/ltx_continuation_client.py) first runs
qualification, then validates receipts, anchor equality and preview bytes
before committing each `manifest.jsonl` row. Never start the sink from an
unverified arbitrary MP4 directory and call it an exact replay.

The [sink](../../experiments/ltx25-b70/stream/ltx_rtmp_sink.py) can render locally
without any RTMP credential. In a separate terminal on the reconstruction host:

```bash
PY=/home/steve/.venvs/ltx25-baseline/bin/python
export LTX_STREAM_WORKDIR=/absolute/new/stream-work
"$PY" -B experiments/ltx25-b70/stream/ltx_rtmp_sink.py \
  --manifest "$LTX_STREAM_WORKDIR/manifest.jsonl" \
  --out "$LTX_STREAM_WORKDIR/view.flv" \
  --state "$LTX_STREAM_WORKDIR/sink-state.json" \
  --stats "$LTX_STREAM_WORKDIR/sink-stats.json" \
  --workdir "$LTX_STREAM_WORKDIR/sinkwork" --size 768x768 \
  --decode-threads 2 --title 'LTX 2.5 continuation: 256x256 native, four B70s'
```

For live forwarding, the repository contains
[start-sink.sh](../../experiments/ltx25-b70/stream/start-sink.sh) and
[relay.sh](../../experiments/ltx25-b70/stream/relay.sh). The sink sends to a local
RTMP relay; the relay obtains an optional remote URL from a private file outside
Git. These wrappers contain originating-host paths (including a legacy working
directory), so adapt a reviewed copy for another host. No stream key is needed
for local files. The direct local sink command above has no disposal option;
`start-sink.sh` has its own legacy directory-disposal defaults. Review both client
and sink retention settings before launch and keep the raw exactness evidence.
Display encoding is not the tensor quality oracle.

Stop new client submissions with one SIGINT and wait for the in-flight chunk.
For the systemd-managed server, gracefully stop its captured, exact unit only
after the client drains, then let the sink finish its current clip. The named
135 server unit is `ltx135-stream-server-20261010`; 137 uses
`ltx137-stream-server-20261010`. No kill-by-pattern or forced GPU termination.
The [ops controller](../../experiments/ltx25-b70/stream/ops/stream_ops.py),
[swap wrapper](../../experiments/ltx25-b70/stream/ops/swap-to-packet.sh) and
[resume wrapper](../../experiments/ltx25-b70/stream/ops/resume-production.sh)
record the originating host's controlled transition procedure. They stop,
archive and launch services, and are not passive verification commands.

## Verify exactness and measure fairly

From a clean repository checkout, this offline audit needs only Python's standard
library. It opens no device, contacts no endpoint and imports no model runtime:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B \
  repro/ltx25-continuation-stream-b70-145f-20261010/verify-evidence.py
```

The native qualification requires three chunks each through eager, graph and
repeat chains, all latent/image/waveform/anchor outputs exact, and unchanged
packet 121 reference hashes. Per-chunk cone/display last-frame equality remains
mandatory during streaming. See the frozen
[GC60 verdict](evidence/135-gc60-stream-qualification-verdict.json),
[GC10 verdict](evidence/135-gc10-stream-qualification-verdict.json),
[qualification implementation](../../experiments/ltx25-b70/recovery/20261010-continuation137-stream/qualification_gate.py)
and [pinned 145-frame reference provenance](../../experiments/ltx25-b70/recovery/20261010-continuation137-stream/reference-frame-145-provenance.json).
“Every chunk exact” is limited to the recorded cone/display comparison and
explicit cross-packet digest comparisons; a three-chunk qualification does not
prove that all future prompts match an independently recomputed oracle.

For timing, collect client logs and all receipts without changing existing runs.
For **each invocation**, take every consecutive submit-to-submit interval whose
destination sequence is at least 10 and whose endpoint precedes that invocation's
first logged pacing hold. Use the complete prefix, including slow intervals.
Never bridge resumes, choose a fast subset, subtract rounded hold durations,
or add medians of overlapping timing buckets. Report count, median, arithmetic
mean and nearest-rank p90; divide by `(frames−1)/24` for work/video. Retain raw
cadence, holds and hold-free diagnostics separately. A short prefix cannot
establish sustained unthrottled speed.

| Packet 135 window | Periods | Median s | Mean s | P90 s |
| --- | ---: | ---: | ---: | ---: |
| GC60 early unthrottled, destinations 10–61 | 52 | 5.2415 | 5.3864 | 5.8150 |
| GC10 early unthrottled, destinations 10–61 | 52 | 5.2415 | 5.3642 | 5.7640 |
| GC60 whole-session raw delivery cadence | 111 | 5.2480 | 5.7275 | 5.9190 |
| GC10 whole-session hold-free diagnostic | 700 | 5.5255 | 5.5325 | 6.0230 |

GC10 raw cadence includes 47 held intervals and has median 5.553 seconds over
747 periods. Removing those holds does not recover the early median. Later
drift and pacing effects are not isolated; no speed win is attributed to GC10,
the storage repair or the F32 scan alone. The fixed [scene schedule](../../experiments/ltx25-b70/data/stream/kittens-01.json)
is hash-bound in this guide’s manifest. The wrapper uses this schedule; the client’s
default seed is `11200000 + stream_seq`, with four chunks per scene unless the
schedule specifies otherwise. Fixed scene/seed continuation and exact conditioning
reuse between scene cuts are part of this workload. It is
not the cold varied-prompt LLM benchmark and carries no LLM tokens/s or prefill
claim. Prompt-encoding timing for this exact profile is not separately measured.

The [promotion attestation](promotion-attestation.json) binds the frozen speed
and quality files and deliberately leaves unsupported gates false. Exact tensor
checks pass; owner acceptance of seams/audio, a registered varied-task video
quality decision, and matched fresh-server speed/repeat certification remain
open. The qualification verdict itself says seam quality and audio alignment
are not accepted. The public strict featured metric must remain unset.

## Progression and limits

[video-measurements.json](video-measurements.json) preserves each measured
configuration separately. The compact history below points to the same frozen
intervals; these are separate settings/windows, not isolated A/B improvements.

| Packet | Change / disposition | Unthrottled prefix median and samples |
| --- | --- | --- |
| 117 | Cone anchor and preparation overlap, 97 frames | 4.762 s per 4 new seconds; n=124 |
| 117 | 121 frames, graph off, later saved session | 5.205 s per 5 seconds; n=163 |
| 118 / 118b | 118 withdrawn at CPU review; 118b fingerprint guards | 118b 121-frame graph-off sessions 5.195/5.279/5.263 s; n=91/261/157 |
| 119 | 121-frame graph/display scheduling; near-floor safety overhead | 5.435 s per 5 seconds; n=51 |
| 120 | 121-frame display replica | 5.092 s per 5 seconds; n=125 |
| 121 | 145 frames, eager cone | First session 5.666 s per 6 seconds; n=316 across separate invocation prefixes; preview/storage incidents retained |
| 122 / 123 | Admission, previews and residency preparation | No separate native stream result |
| 123b | Run-owned storage; legacy 145-frame control | 5.770 s per 6 seconds; n=51 |
| 123b | 169-frame auxiliary-placement diagnostic | 6.824 s per 7 seconds; n=39 |
| 124 / 125 | Parallel display / GC60 experiment | 5.746 / 5.785 s per 6 seconds; n=35/207 |
| 126 | Background storage scans | 5.697 s per 6 seconds; n=202 |
| 127 | Digest cache and GC60 at 145 frames | 5.467 s per 6 seconds; n=85; client resume incident retained |
| 128 | Idle maintenance; GC10 / GC60 | 5.4925 / 5.528 s per 6 seconds; n=60/61 |
| 129 | Atomic publication of evidence | First session 5.486 s per 6 seconds; n=91; other sessions retained in JSON |
| 130 / 131 / 132 | Memory remedies | 130 not launched; 131/132 refused memory during qualification; no speed point |
| 133 / 133b | Text split makes 145-frame cone graph fit | 133 import failed before launch; 133b first/repeat prefixes 5.221 / 5.411 s, n=47/71; first session storage halt retained |
| 134 | 169-frame graph-off candidate | Not launched; forecast excluded |
| 135 | Storage link-accounting repair | GC60 and GC10 both 5.2415 s per 6 seconds, n=52 each |
| 136 | No distinct native receipt in this evidence packet | Not measured here |
| 137 | Bulk F32 predicate | Startup/CPU evidence only here; no borrowed 135 rate |

Read the [full campaign history](../../notes/2026-10-10-ltx-continuation-campaign.md)
and [result ledger](../../results/ltx25-continuation-stream-2026-10-10.md)
for rejected and superseded paths. Historical raw timing in those notes must
not override the pacing rule and frozen arrays above.

Keep physical-free admission floors **8/8/2/9 GiB** on cards 0/1/2/3, and
2 GiB/card post-request. Cone capture retains its full 5 GiB reserve and
0.75 GiB screening band. The storage floor is 50 GiB plus the declared
16 GiB run write allowance; background accounting retains a 256 MiB pending
write margin. Full snapshots stay enabled. Do not reduce these to make a run fit.
The [133b memory audit](../../experiments/ltx25-b70/notes/2026-10-10-continuation133b-results-145.md)
records observed physical-free minima 9.27/9.83/4.91/14.60 GiB over its
31-receipt window, not peak VRAM or a guaranteed minimum for all streams.

Single-queue B70 execution is the tested scope: concurrent requests, different
card counts, arbitrary new prompts under the split36 oracle, longer frame
geometries and a portable fresh-host install are not certified. Full-frame
parity against this distilled checkpoint does not establish parity with the
distinct dev model, CUDA, another precision or another runtime. On a fault or
refusal preserve the evidence and halt new work; never clear latches, change
power/swap settings, reset drivers or reboot as part of this recipe.
