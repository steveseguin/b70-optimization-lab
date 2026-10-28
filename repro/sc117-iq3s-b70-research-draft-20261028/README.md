# SC117 IQ3_S on B70: reproduction draft 2026-10-28

**Draft research recipe, not a production or beginner-ready release.** This packet
pins the source, models, workloads and operating profiles behind the recent AOT
and dedicated-draft experiments. The source can be exported and built; the latest
dedicated-draft hardware replay still needs a portable controller/observer adapter.
The older portable bounded replay is available separately. These distinctions are
intentional; the missing gates are in [publication-manifest.json](publication-manifest.json).

The model is **SC117 Qwen3.8 Flash Next GSQ-RCO IQ3_S mixed quantization**,
with the existing official FP8 draft. This is the lab's own SYCL runtime.
Target activations, recurrent arithmetic and attention KV storage remain F32. No draft training, lower-precision KV or prompt/response reuse.

## Latest results and frozen recipe scope

See the [shareable engine diagram](assets/engine-explainer.png) and
[explanation with quantization ratios](EXPLAINER.md).

Read the [October 28 results](RESULTS.md) for the twelve-prompt depth comparison,
CPU-qualified outputs, three-card reset gate and long-prompt placement tradeoff.
Those later results have their own source/binary identities; this build recipe
keeps its earlier source pin.

## Historical measurements reproduced by this source

Each row is one first-inference request with **121,854 actual prompt tokens and
512 outputs**. Reserved capacity is not the tested input length.

| Profile | Cards | Target layer cuts | Reserved context | Request seconds | TTFT seconds | Decode, all 511 intervals |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| 2 target + 1 draft | 3 | 0 / 25 / 48 | 131,072 | 369.931 | 358.558 | 44.962 tok/s |
| 3 target + 1 draft | 4 | 0 / 17 / 33 / 48 | 262,144 | 261.330 | 250.742 | 48.296 tok/s |

Both use BMG-G31 AOT, 256-row batched prefill, four transport slots, pipelined
target/draft prefix processing, depth-three verified speculation, and capture-ready
draft handoff. The 3+1 row uses **29.357% less request time** than the 2+1 row;
card count, placement and context reservation all differ. Startup and shutdown
are excluded. This is a single long-input screen, not a realistic-suite score,
context curve, independent-reference quality result or LocalMaxxing record.

The retained comparison matched all 512 outputs, 2,065 target sources, 73 draft
sources and 122,364 actual hidden/token pairs. [Measurements](measurements.json)
retain the exact scope. The pinned source predates the latest router-tie
diagnostic: its six historical independent CPU-reference disagreements remain
unresolved by this packet. Matching the expected GPU output below does not settle
them. Later optimization work continues independently.

## 1. Obtain the draft and freeze the source

Use a new checkout for this recipe. Existing experiment checkouts need not change.
Git, Python 3.12, curl and the platform dependencies in [SETUP.md](SETUP.md) are
required. Python helpers use only the standard library and token IDs; a tokenizer
package is unnecessary for these fixed inputs.

```bash
git clone --filter=blob:none --sparse --branch sc117-repro-draft-20261028 https://github.com/steveseguin/b70-optimization-lab.git sc117-repro
cd sc117-repro
git sparse-checkout set repro/sc117-iq3s-b70-research-draft-20261028 experiments/own-xpu-runtime/engine
git fetch --no-tags origin ba563d432dc616e11232fc90eec54338cc358b18

RECIPE="$PWD/repro/sc117-iq3s-b70-research-draft-20261028"
python3 -B "$RECIPE/recipe.py" verify
python3 -B "$RECIPE/recipe.py" export-source --repo "$PWD" --output "$PWD/../sc117-source-draft"
SOURCE_ROOT="$(cd ../sc117-source-draft && pwd)"
ENGINE="$SOURCE_ROOT/experiments/own-xpu-runtime/engine"
python3 -B "$RECIPE/recipe.py" verify --source-root "$SOURCE_ROOT"
```

The tag freezes this draft's instructions. The exporter reads immutable Git objects at **ba563d432dc616e11232fc90eec54338cc358b18**,
not the current checkout or index. It refuses an existing destination. The
[source inventory](source-inputs.json) pins every exported file and runtime asset.
[Source audit](source-audit.json) matches all **256 native dependencies** against
the measured binary's receipt. The canonical AOT build option was added after
that measurement; its recipe preserves the AOT target and compile/link flags.
A relocated build with a newly authenticated model binding is a new binary and
must pass its own gates. Binary bit identity is not promised.

Keep the extracted source at its build location: native code reads the RoPE
table there. The inventory includes both 65,536- and 262,144-position tables;
the historical build receipt only lists the former although this source reads
the latter. The draft's complete source hashes cover both.

## 2. Download the exact model files

[model-downloads.json](model-downloads.json) lists direct revision-pinned URLs,
filenames, sizes and SHA-256 hashes. Target shards are under **IQ3_S/** upstream,
but are saved as flat filenames in the local target directory. The source profile
contains local basenames; blindly appending them to the upstream root gives 404.

- Target: two GGUF files, **83,863,586,496 bytes**.
- Draft: 28 complete safetensors shards, **30,047,461,616 bytes**. The selected
  tensors total about 2.7 GB, but the current loader requires the complete shards.
- Tokenizer: optional for these token-ID workloads; needed for a future text flow.

Choose real filesystem paths with space for these files, source, build output and
runtime evidence. This helper prints a shell script; it does not download anything.
Inspect it before running it. Interrupted `.partial` files are retained and the
script refuses existing files rather than silently overwriting them.

```bash
MODEL_FILES=/absolute/path/to/sc117-model-files
python3 -B "$RECIPE/recipe.py" download-plan --root "$MODEL_FILES" > download-models.sh
# Review the generated URLs, destination and storage needs, then:
sh download-models.sh
```

Every file must pass SHA-256 before its `.partial` name is promoted. No credential
is embedded or required by the generated script. [Upstream check](upstream-check.json)
records matching public sizes/LFS hashes for all 30 weight shards and representative
HEAD responses; this release did not redownload or hash the full model payloads.

## 3. Authenticate a local binding and build

First follow [SETUP.md](SETUP.md). Use real absolute, non-symlink paths, an existing
destination parent, and new deployment/build directories. Preparation authenticates
all target and draft files; it can take time and does not launch a GPU.

```bash
PROFILE_SHA=369ea09fc13015721df09a02841d5ef368d24455f25957d8fc2187e07a96999a
DEPLOYMENT=/absolute/path/to/new-sc117-deployment
BUILD=/absolute/path/to/new-sc117-build
ICXX=/opt/intel/oneapi/compiler/2026.0/bin/icpx

python3 -B "$ENGINE/deployment/prepare.py" \
  --profile "$ENGINE/profiles/sc117-iq3s/profile.json" --profile-sha256 "$PROFILE_SHA" \
  --model-root "$MODEL_FILES/target" --draft-root "$MODEL_FILES/draft" \
  --output "$DEPLOYMENT" --plan-only

nice -n 19 python3 -B "$ENGINE/deployment/prepare.py" \
  --profile "$ENGINE/profiles/sc117-iq3s/profile.json" --profile-sha256 "$PROFILE_SHA" \
  --model-root "$MODEL_FILES/target" --draft-root "$MODEL_FILES/draft" \
  --output "$DEPLOYMENT" --seconds 7200

BINDING_SHA="$(sha256sum "$DEPLOYMENT/binding.json" | cut -d ' ' -f 1)"
nice -n 19 python3 -B "$ENGINE/build.py" "$BUILD" --name sc117-engine --jobs 4 \
  --compiler "$ICXX" --aot-target intel_gpu_bmg_g31 \
  --generated-include "$DEPLOYMENT/include" \
  --profile-sha256 "$PROFILE_SHA" --deployment-sha256 "$BINDING_SHA"
```

This compilation command is supplied for the reader; this draft release did not
run a new full-engine build or device job. The exported [deployment documentation](../../experiments/own-xpu-runtime/engine/deployment/README.md)
explains binding checks and the older portable target-only controller. Its small
two/four-stage replay and [live-MTP recipe](../../experiments/own-xpu-runtime/engine/deployment/LIVE.md)
have earlier same-host evidence. They use a different launch policy and **do not
reproduce the latest dedicated 2+1 / 3+1 speed numbers**.

## 4. Latest dedicated-draft configurations: expert adaptation required

The [2+1](configs/2plus1.json) and [3+1](configs/3plus1.json) templates retain the
recorded topology and resource floors. Their safe initial policy is qualification;
they contain no copied local admission, credentials, PCI address or model path.
The helpers can materialize exact input/configuration files after an expert has
created a valid local adapter plan and build receipt.

**The blocker:** `dedicated_provider_driver.py` still takes an
`ownrt.gsq.rank-adapter-plan.v1` adapter. Its observer uses originating-host
credentials, boot/fault state and queue paths. The portable launch planner does
not yet produce an interchangeable dedicated adapter. Do not copy the recorded
admission, invent local identity hashes, disable the observer, or remove checks
to force a run. The draft does not ship a replacement GPU launcher.

Once that integration is qualified, this configuration command is ready to use.
Replace the example PCI addresses with independently identified physical devices:

```bash
python3 -B "$RECIPE/recipe.py" configure \
  --profile 2plus1 --workload short --policy qualification \
  --adapter /absolute/path/to/qualified-local-adapter.json \
  --receipt "$BUILD/build-receipt.json" \
  --target-bdf 0000:23:00.0 --target-bdf 0000:47:00.0 \
  --provider-bdf 0000:43:00.0 --output /absolute/path/to/new-short-input
```

For 3+1, select `--profile 3plus1` and provide three `--target-bdf` arguments.
The helper creates `config.json`, `prompt.json`, and little-endian `prompt.i32`.
It does not grant runtime admission or validate the supplied adapter's behavior.
No expected output is written into the configuration or passed to the engine.

The exact measured kernel environment is preserved separately in
[2+1](configs/2plus1-measured-environment.json) and
[3+1](configs/3plus1-measured-environment.json). Matching the config alone is
insufficient: preserve environment, build identity, model binding, cold input,
dispatch, arithmetic, allocation cap and timing observer. Use one loaded process
lifetime per admitted experiment, never an automatic restart/retry chain.

After qualification, `--workload long --policy measured` materializes the exact
121,854-token/512-output timing case, disabling expensive verification only as in
the measured arm. This is an explicit configuration choice, not evidence that a
new build passed qualification. Floors remain 96 GiB available RAM at start,
8 GiB running, 27 GB root free and 2 GiB evidence free. Those are admission
minimums, not forecasts of sufficient peak dump/storage headroom.

## 5. Check a result and retain its identity

After a separately admitted run has completed and every owner has drained:

```bash
python3 -B "$RECIPE/recipe.py" check-output \
  --workload short --tokens /absolute/path/to/run/tokens.jsonl
```

Use `--workload long` for the 512-output case. This catches missing, reordered or
different tokens and returns nonzero on failure. Expected tokens are historical
GPU-baseline outputs, not independent CPU truth. Output matching alone is not
the complete-state gate: the existing target/draft state comparators also need
fresh qualified reference dumps. Large historical state bundles live outside Git;
we publish their receipts, not an assertion that readers can download those bundles.

Retain source/model/binary hashes, local build and runtime-library inventory,
configuration, complete command/environment, actual input/output counts, no-cache
evidence, first/last token timestamps, full state comparison, final process exit
codes and passive postflight. A fault halts new requests; stop cooperatively once,
retain the evidence, and investigate. There is no resident HTTP health endpoint in
this one-shot draft. No host reboot, driver reset, power or memory-setting changes
are part of this recipe.

## Completion work for the later release

1. Complete and qualify the dedicated-provider portable adapter and observer.
2. Lock and test the installation on a clean supported host; record complete
   compiler/runtime packages and shared-library resolution.
3. Repeat short full-state gates, realistic cold workloads and long timing using
   newly generated local bindings; include a publicly regenerable reference path.
4. Resolve independent-reference quality and repeat the tests for any changed code.
5. Publish verified binary/build-log assets if desired, then earn the complete
   publication and clean-host certification statuses. All three certification
   booleans remain false in this draft.

This packet was checked using CPU-only helpers, source hashes and public metadata.
See [validation.json](validation.json) for actual checks. It deliberately freezes
the measured optimization revision while development continues.
