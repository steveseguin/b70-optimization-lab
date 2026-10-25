# Prepare the current SC117 model at a new local path

The CPU-only preparation step authenticates the **existing SC117 IQ3_S target** and,
optionally, the existing official FP8 draft. It creates a separate local build
authority without editing canonical engine source. It does not train a draft,
download weights, install software, launch an engine, or certify output quality.
The implementation has synthetic CPU and native authority tests. The current
model was fully authenticated once and built from the frozen `f6079c380` source
archive with its generated authority on the existing host; see the retained
[authentication and build receipts](../../research/continuation-2026-10-25/portable/).
The standalone launcher subsequently passed bounded
[two-card](../../research/continuation-2026-10-25/portable/pp2-proof/RESULT.md) and
[four-card](../../research/continuation-2026-10-25/portable/pp4-proof/RESULT.md)
target-only replays: the same 87-token prompt, 32 exact outputs and all 2,065
canonical target buffers/layouts matched the retained baseline. A clean-host
installation, changed model-file location, portable chat service and performance
qualification remain open. These runs do not resolve the six independent CPU
reference disagreements.

The immutable [profile](../profiles/sc117-iq3s/profile.json) identifies:

- Target: `SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF`, revision
  `eec4e10a2c29b440a2ae85591fa11569ce752963`, two complete GGUF files totaling
  **83,863,586,496 bytes**, 1,224 descriptors, exact header hashes and payload bases.
- Optional draft: `Qwen/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, **28 complete safetensor shards totaling
  30,047,461,616 bytes**. Its 3,101 selected tensor payloads total 2,698,026,496
  bytes, but the current loader requires the full source shards.
- Optional text tokenizer: `tokenizer.json` from the same official revision,
  pinned by SHA256. The retained chat template comes from the target GGUF census.
  This tool authenticates these files; it does not install a tokenizer library or
  provide a portable chat service.

Obtain these exact filenames from the pinned repositories before preparation.
The profile lists every required file and full SHA256. No model format conversion
or repacking is involved. Keep the deployment metadata and source tree available
for the entire lifetime of any engine built from them.

## Trust and local binding

The release profile's SHA256 is:

```
369ea09fc13015721df09a02841d5ef368d24455f25957d8fc2187e07a96999a
```

Use this digest only after establishing that this recipe/repository revision is
trusted. Recomputing a digest from an untrusted downloaded profile is not an
independent trust anchor. The adjacent `profile.sha256` is a convenient checksum,
not a signature. The profile has no local inode, device number, timestamp, GPU
mapping, model root or output path. Its separately hashed TSV assets contain the
complete trusted target descriptors and draft payload identities.

Preparation checks full file hashes using 4 MiB reads, held regular-file
descriptors, no-symlink path traversal, and before/after stat identity checks.
Draft payload hashes are also checked individually. A missing, changed, replaced,
symlinked or incorrectly sized file fails preparation. The output directory must
be new. A failure never produces a valid final `binding.json`; preserve partial
output as evidence and investigate before choosing another output location.

The generated local binding contains absolute paths and stat identities. Do not
publish it as a reusable model profile. Subsequent native admission still checks
the compiled descriptor authority, placement/auth hashes, exact header hashes,
and local shard identities. A model or location change requires fresh full
authentication, a new overlay build and runtime qualification. These checks do
not protect against an adversary controlling the user's account or the build
toolchain.

## Inspect the work without reading model payloads

Run from the repository root. Select paths appropriate for the local deployment:

```bash
ENGINE=experiments/own-xpu-runtime/engine
PROFILE_SHA=369ea09fc13015721df09a02841d5ef368d24455f25957d8fc2187e07a96999a
MODEL_ROOT=/path/to/sc117-iq3-s
DEPLOYMENT=/path/to/new/sc117-deployment

python3 "$ENGINE/deployment/prepare.py" \
  --profile "$ENGINE/profiles/sc117-iq3s/profile.json" \
  --profile-sha256 "$PROFILE_SHA" \
  --model-root "$MODEL_ROOT" --output "$DEPLOYMENT" --plan-only
```

The plan reports source/destination filesystem device identities and available
space, full-file and additional verification byte budgets, intended artifacts,
and the 4 MiB read bound. It reads only small profile assets and local file stats;
it creates nothing and reports `full_content_authenticated=false`. The destination
parent must already exist. This is a storage plan, not permission to interrupt
an active service or change host memory/power settings.

For draft/text preparation add explicit roots to the same command:

```bash
  --draft-root /path/to/official-fp8 \
  --tokenizer-root /path/to/official-tokenizer
```

The target-only path does not require either optional root. The tokenizer file
may share a directory with the official draft shards.

## Authenticate once, then build the local authority

After scheduling the bounded read pass for the deployment, run the same
preparation command with `nice -n 19`, optional `ionice -c 3`, and without
`--plan-only`. No automatic retries are performed. The default deadline is
7,200 seconds; `--seconds` accepts 1 through 86,400 seconds. Large model
authentication refuses a process whose nice level is not 19.

```bash
nice -n 19 ionice -c 3 python3 "$ENGINE/deployment/prepare.py" \
  --profile "$ENGINE/profiles/sc117-iq3s/profile.json" \
  --profile-sha256 "$PROFILE_SHA" \
  --model-root "$MODEL_ROOT" --output "$DEPLOYMENT" --seconds 7200

sha256sum "$DEPLOYMENT/binding.json"
```

Record the printed binding digest as `BINDING_SHA`. It identifies this verified
local binding, separately from the immutable profile digest. Build in a fresh
directory with enough space for object files:

```bash
BINDING_SHA=the_recorded_64_character_binding_digest
nice -n 19 python3 "$ENGINE/build.py" /path/to/new/build \
  --jobs 4 --generated-include "$DEPLOYMENT/include" \
  --profile-sha256 "$PROFILE_SHA" --deployment-sha256 "$BINDING_SHA"
```

The sole permitted overlay is
`include/gsq-rco-iq3s/integration/build/private/additive/bound.hpp`. The builder
regenerates its expected bytes from the pinned profile/local binding, rejects
extra headers, puts that include root before canonical `src`, verifies the
compiler actually used it, and records canonical versus generated dependencies
separately. Canonical `bound.hpp` is preserved. Omitting all three overlay options
uses the existing host-bound build path.

The existing build manifest uses Intel oneAPI compiler 2026.0, Level Zero loader
and OpenSSL, with its retained compiler/link flags. `--compiler /absolute/icpx`
can select the installed compiler explicitly; it is recorded in the build
commands. This recipe does not claim a validated compiler/runtime installation
procedure on a clean host. Keep the source tree at its build path: native code
currently reads the pinned 4 MiB `rope.bf16` beside its compiled `main.cpp`.
The build receipt records this runtime asset too. Copying only the executable
to another location is not a complete deployment.

## Runtime integration still to qualify

The CPU-only [launch-plan generator](launch_plan.py) generates concrete native
arguments and environments directly from this binding, without importing a
recorded lab adapter. It supports two/four-stage target-only command templates
and the existing two-rank MTP command templates. Its separate
[launch policy](../profiles/sc117-iq3s/launch-policy.json) pins the existing
[dispatch choices](../profiles/sc117-iq3s/dispatch-f32-select-gdn2.json), F32 target
flags, 23/25 or 13/12/12/11 layer placement, and existing draft kernel choices.
The policy SHA256 is embedded in the generator. MTP templates use the unchanged
official draft weights, scalar prefill and `OWNRT_EARLY_RANK1=0`; they make no
claim to reproduce the fastest service timing.

After building the generated authority, record the build receipt's SHA256 and
provide explicit runtime-library directories and PCI BDFs. This example writes
a plan only; the BDFs and paths are examples, not hardware discovery:

```bash
BUILD_RECEIPT=/path/to/new/build/build-receipt.json
RECEIPT_SHA=the_recorded_64_character_build_receipt_digest
python3 "$ENGINE/deployment/launch_plan.py" \
  --deployment "$DEPLOYMENT" --profile-sha256 "$PROFILE_SHA" \
  --binding-sha256 "$BINDING_SHA" --build-receipt "$BUILD_RECEIPT" \
  --build-receipt-sha256 "$RECEIPT_SHA" \
  --bdf 0000:23:00.0 --bdf 0000:47:00.0 \
  --library-dir /opt/intel/oneapi/compiler/2026.0/lib \
  --library-dir /path/to/other/required/runtime/lib \
  --prompt-tokens /path/to/prompt-token-ids.json --max-new 32 \
  --output /path/to/new/run --plan /path/to/new/launch-plan.json
```

Supply four distinct BDFs for four target stages. `--mode mtp` selects the
existing two-rank protocol and requires a fully authenticated draft binding.
That legacy template is capped at 128 generated tokens and has no shipped portable
controller. For the separate live pipeline protocol, use the experimental
[LIVE.md recipe](LIVE.md); its default qualification request is 32 tokens.
A 512-token pipeline template requires the newer pipeline-capable native parser,
not an older executable merely receiving a larger Python setting.
It uses one shared pair region; target-only stages use separate shared regions.
Each stage's native output is the initially absent `stageN/native` child, distinct
from the controller's IPC/cache/log directory. Environments are assembled from
the pinned policy and explicit runtime paths; arbitrary inherited diagnostic or
preload variables are not carried over. The planner verifies binary, receipt,
generated authority, runtime RoPE asset and current local model stat identities.
It does not open a GPU or read model payloads.
Each command explicitly invokes the hash-pinned `/usr/bin/ionice -c 3` wrapper.
The plan also requires the controller to check its own nice level is exactly 19
before spawning children; native `--native-nice 19` independently rejects a child
at a different level. These are process-priority requirements, not host power
settings. The planner itself changes neither.

The resulting `ownrt.portable-launch-plan.v1` has `stages[].argv`, `environment`,
`native_output`, `bdf`, `first`, `final`, `begin` and `end`, plus hash pins and
protocol identity. Its `run_authorized=false` remains correct: **a plan is not
runtime admission**. The foundation plan's `portable_observer_available=false`
records that release's scope. The separate experimental
[controller](controller.py) and [passive observer](observer.py) now provide a
target-only execution path with CPU tests and the bounded two/four-card replay
evidence above. They
regenerate the commands from the trusted generator and reject changed commands,
environments, profile/binding/build inputs, runtime assets or local shard stats.
The MTP templates are not accepted by this controller.

Validate a target-only plan without opening GPUs:

```bash
PLAN_SHA=the_recorded_launch_plan_digest
python3 "$ENGINE/deployment/controller.py" \
  --plan /path/to/launch-plan.json --plan-sha256 "$PLAN_SHA" \
  --profile-sha256 "$PROFILE_SHA" --binding-sha256 "$BINDING_SHA" \
  --build-receipt "$BUILD_RECEIPT" --build-receipt-sha256 "$RECEIPT_SHA"
```

Execution additionally requires explicit `--run --admission /path/to/admission.json`
and either `--coordinator-stop-fd FD` or the name of the controller's own user
systemd unit via `--unit NAME`. The unit must have `Restart=no`,
`KillMode=process`, `SendSIGKILL=no` and matching invocation/PID. Run the controller
at nice level 19. It launches each stage once, tracks PID/start-time identity
before further work, uses cooperative stop pipes, and reports surviving processes
instead of killing, resetting or restarting them. A fault, unknown inventory,
changed hardware identity, resource-floor breach or deadline halts new commands.
The replay dumps final state and records postflight; it makes no speed claim.

Admission has schema `ownrt.portable-run-admission.v1`, `owner_authorized:true`,
`plan_sha256`, independent `controller_sha256` and `observer_sha256`, a timezone-
qualified `expires_utc`, reviewed `baseline` path and `baseline_sha256`, an
`observer_backend`, and `limits` containing integer `memory_start_bytes`,
`memory_floor_bytes`, `root_floor_bytes`, `evidence_floor_bytes`, `grace_seconds`.
Set floors for the actual host and workload; the tool's minimums are not a memory-
fit estimate. Baseline creation does not authorize accepting a new hardware fault.
Review any historical faults before explicitly binding that baseline in admission.

The standalone observer only reads `/proc`, sysfs, device-node metadata and the
kernel journal. It never opens a DRM node or invokes a GPU API. It records PCI
vendor/device/subsystem/revision identities, card/render aliases and process
start ticks. This establishes the observed PCI identity and ownership, not a
marketing-name or capacity certification. Process/FD census and kernel-journal
reads have count, size and time limits; missing other-user FD permissions or
truncated/unavailable evidence fail closed.

Select `direct-root` only when the controller already has the needed privileges,
or `sudo-n` for a preconfigured noninteractive observer invocation. No password
file or privilege configuration is provided. An explicit local credential broker
can instead use `external-wrapper`: admission must pin an absolute
`observer_wrapper` and its `observer_wrapper_sha256`. The wrapper receives exactly
one argument, the packaged observer script path, and must emit only that root
observer's JSON to stdout. Keep such a broker outside the source package and
protect its credentials locally. Helper failure never falls back to an empty
inventory, interactive prompt or alternate privilege method. Privilege policy is
an operator prerequisite; this recipe does not modify sudoers.

New deployment runs must establish token and full-state parity before reporting
performance. The current native capability remains the existing
48-layer Flash-Next architecture, F32 target activations and context 4,096.
Profiles do not bypass decoder, geometry, arithmetic, memory or admission checks.

CPU validation (no real model reads or GPU calls):

```bash
python3 -m unittest discover -s "$ENGINE/deployment" -p 'test_*.py'
python3 -m unittest discover -s "$ENGINE/release" -p 'test_*.py'
```
