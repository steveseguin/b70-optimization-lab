# Portable SC117 recipe: concrete remaining work

Read-only implementation audit, 2026-10-25. No native changes or hardware actions.
The canonical source builds on the current host; the following is the shortest
route to a reproducible deployment elsewhere, not a claim that this route already
exists. Keep portable cryptographic model identity separate from local paths and
filesystem identities. Do not relax arithmetic/model capability checks.

## Release inputs already available

- Target [model-identity.json](../../gsq-rco-iq3s/model-identity.json) pins repository
  `SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF`, revision
  `eec4e10a2c29b440a2ae85591fa11569ce752963`, both filenames, full SHA256 and byte
  sizes. Total target download: **83,863,586,496 bytes**. The
  [placement](../../gsq-rco-iq3s/loader/placement.tsv) and
  [metadata census](../../gsq-rco-iq3s/metadata/new-census.json) retain all 1,224
  descriptors and exact header/tokenizer/architecture information.
- Draft [source identity](../../gsq-rco-iq3s/mtp/source-audit.json) pins
  `Qwen/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`.
  [draft-manifest.tsv](../../gsq-rco-iq3s/mtp/draft-manifest.tsv) identifies 3,101
  required tensors totaling **2,698,026,496 bytes**, spread across **28 complete
  safetensor shards totaling 30,047,461,616 bytes**. Do not advertise 2.7 GB as the
  existing loader's download size. The historical
  [prepare_mtp.py](../../stage2/packet36-draft/prepare_mtp.py) authenticates complete
  source shards against [tensor-contract.json](../../stage2/packet1/tensor-contract.json),
  then hashes exact MTP payload slices. It is useful implementation material, but
  currently hardcodes this host and writes historical evidence paths.
- Text input requires the same revision's `tokenizer.json`, pinned to SHA256
  `0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3`
  by [coverage/tokenizer.py](../../gsq-rco-iq3s/coverage/tokenizer.py). Full vocabulary,
  merges and chat-template hashes are already checked against the target census.
  Explicit token-ID input can qualify the engine before packaging the chat layer.
- [build.py](../build.py), [build-manifest.json](../build-manifest.json), complete
  `src/`, retained dispatch profiles and state/token tests exist. Build receipts
  record actual compiled dependency hashes; consolidation hashes are historical.

## Blocking dependencies and fixes, in order

1. **Target identity is compiled together with one machine's deployment.**
   [Canonical bound.hpp](../src/gsq-rco-iq3s/integration/build/private/additive/bound.hpp)
   pins `/home/steve/...` placement/auth paths, `/mnt/usb-models/...` model root,
   and old device/inode/mtime/ctime values. An identical SHA256 download at a new
   path still fails. [generate_bound.py](../../gsq-rco-iq3s/loader/generate_bound.py)
   hardpins the old auth/census hashes too, while
   [prepare_inputs.py](../../gsq-rco-iq3s/loader/prepare_inputs.py) requires the old
   stat identities. They are frozen provenance tools, not a relocatable preparer.
2. **Draft files are also deployment-bound.** The manifest combines immutable
   tensor offsets/types/dimensions/payload hashes with file dev/inode/timestamps.
   The current [MTP Store](../src/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/mtp.hpp)
   checks those identities and actual tensor hashes. Add a local rebind tool that
   verifies pinned full-shard hashes and every required payload before generating
   new stat fields. Keep original manifest/evidence unchanged. Compact MTP-only
   shards could reduce download later, but need a separate authenticated repacker
   and loader manifest; arbitrary repacking is not currently supported.
3. **No independent relocatable launch profile yet.**
   [adapter6.py](../../gsq-rco-iq3s/serving/lan/adapter6.py) imports historical
   P195/packet181 paths and hardcodes model roots/BDFs. The new
   [pipeline driver](../tools/pipeline_driver.py) deliberately consumes an existing
   recorded adapter plan; that current plan is outside the repository. Replace
   this dependency with a versioned profile containing model/draft/tokenizer
   identities, context, precision, kernel choices, topology and input/output
   policy. Generate argv/environment from that profile and device mapping. Keep
   the local LAN/service/fault baseline as deployment policy, not engine identity.
4. **Toolchain/runtime setup is not yet a clean-host recipe.** The build pins
   `/opt/intel/oneapi/compiler/2026.0/bin/icpx`, `libcrypto`, `libze_loader` and
   rpaths. The [recorded launch environment](../../stage2/packet181-session-swap-v3/one-card/launch_env.py)
   enumerates installed oneAPI compiler/TCM/UMF/TBB/PTI/MKL/DNNL/debugger paths.
   Publish exact package/runtime/driver versions and an installation recipe or
   container with host-driver requirements, then demonstrate a clean build and
   dependency audit. Repository source alone does not recreate those installations.
5. **Text service and startup gates retain host-only inputs.** Tokenizer code
   searches `/home/steve/.venvs/vllm-xpu` for `tokenizers`/Jinja2 rather than a
   project dependency lock. [service.py](../../gsq-rco-iq3s/serving/lan/service.py)
   embeds LAN/subnet/credentials paths, affinity, BDFs, service-unit and coordinator
   paths; passive observer uses the local sudo credential path. Reference raw state
   bundles and active binaries live in external storage/tmpfs. Package the minimal
   hash-bound gate fixtures (or a deterministic reference-generation recipe),
   explicit Python dependencies and configurable local policy. Never distribute
   local credentials, inode receipts or fault baselines as universal configuration.

## Minimal deployment overlay, then runtime manifests

First add a CPU-only `engine/tools/prepare_deployment.py` with explicit inputs:
portable release manifest plus its independently supplied trusted SHA256, model
root, optional draft root, and a fresh output directory. These are proposed paths.
The portable manifest contains full shard SHA256/size, exact header prefix hashes,
placement hash and complete expected descriptors, geometry/quant identities,
draft payload identities and tokenizer/template hashes. It contains no inode,
mtime, device BDF, home directory or output path.

The preparer opens regular files without symlink substitution, verifies full
content against those pinned identities, checks held-FD identity before and after
verification, and writes a separate local deployment binding: canonical paths,
local stat tuples and cryptographic release-manifest identity. It must not use an
unchecked candidate placement as its own trusted expected plan. A cached binding
may accelerate later startup only while the admitted local identities still match;
content changes require independent re-verification.

The least invasive first native integration is a generated include overlay at:

```
DEPLOYMENT/include/gsq-rco-iq3s/integration/build/private/additive/bound.hpp
```

Generate the existing exact authority format from the authenticated portable
profile plus local binding. Add `build.py --generated-include DEPLOYMENT/include`
with this single allowed header path ahead of `engine/src` in include search.
Record overlay dependencies and profile/binding hashes in the build receipt
(the current dependency collector only records paths under `engine/src`). The
old bound loader, header checks and `iq3::Model(..., Admission)` validation remain
unchanged. No canonical header is overwritten. This gets a relocatable build
quickly, at the cost of recompilation and qualification after relocation. Adapt
CPU build tests and the driver's source-pin validation to distinguish canonical
source dependencies from generated authority explicitly.

The lasting interface is a strict runtime admission manifest, e.g. new
`engine/src/model/admission.hpp`, selected by `--model-profile PATH` plus an
independently supplied `--profile-sha256 SHA`. Reuse the existing `iq3::Admission`
structure and loader overload; replace only the fixed `gsq::bound::authenticate`
entry when the new option is selected. Native code verifies profile SHA, descriptor
and header identity, and the local held-file binding before passing the **trusted
expected** descriptors separately from the candidate plan. Keep the legacy compiled
authority path intact while qualifying this change. A profile hash establishes
identity relative to the trusted release digest; accepting an arbitrary user file
without an independent digest must not be described as authenticated provenance.

Target, draft and tokenizer identities should share this portable profile, while
per-tensor decoders, architecture geometry, stage boundaries and measured tuning
stay separate. Start by relocating the exact current SC117 model with all checks
preserved. Next admit another quant using the same architecture and qualify its
per-tensor formats. General model support needs data-driven geometry/capability
validation in addition to replacing paths; it is not achieved by renaming this
model or bypassing the current Flash-Next shape checks.
