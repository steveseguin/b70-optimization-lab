# Absolute-current-main transition and overlay preservation

Date: 2026-08-23. Status: **preservation gate passed; fresh integration tree
required; no legacy source tree will be rebased**.

## Decision

“Nightly” is not sufficient shorthand for current code. Active development
must resolve the literal upstream `main` heads immediately before a build. If
the official XPU nightly image trails upstream, it is only the runtime base and
an official-image comparison lane. The active source identity is a custom
current-main build, labeled with its exact vLLM and XPU-kernel commits.

Accepted lab work is a versioned overlay on that moving base. Updating means:

1. freeze the old code, binaries, results, cache decisions, and performance
   floors;
2. start from fresh clean upstream-main trees;
3. determine whether each accepted behavior is already upstream, still
   required, or conflicts with a redesign;
4. port only still-required accepted behavior, one qualified delta at a time;
5. stop promotion on any identity, quality, graph, cache, determinism,
   acceptance, context, or performance regression.

A conflict never authorizes silently dropping an optimization. A new result
never overwrites a historical high.

## Heads observed at the preservation gate

- official XPU nightly index:
  `sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`;
- official linux/amd64 manifest:
  `sha256:ad7d8e8ef69e3dcc1ad08339b12c0c118bf98b9602b89f66aa5efc236e1df41a`;
- official nightly vLLM source:
  `a3561ef8e49d3545c4078df43444beb4c98ae124`;
- upstream vLLM `main`:
  `cd329413e2bb2086c2c97c373dcc3bd1ff29fa9f` (seven commits ahead of the
  image when audited);
- upstream vLLM XPU kernels `main`:
  `4543b580fecca68a7dd54ddaf6e444dc5f11a6a4`.

These upstream hashes are observations, not aliases. Re-resolve both heads
again immediately before cloning/building because either may move at any time.

The seven vLLM commits between the image and the observed head affected MM
prompt input, arm64 Cython pinning, GPT-OSS, validation errors, RL P2P weight
sync, and Omni encoders. None explicitly touched Qwen, XPU, or MTP. That lowers
the expected port risk but does not waive matched qualification.

## What is protected

The pinned target-only graph frontier used an unmodified official image: no
vLLM source overlay, kernel DSO replacement, code mount, or image mutation.
Its two diagnostic captures at TP1/TP2/TP4 were respectively
`30.2178 / 30.2569`, `48.8301 / 48.950458800865434`, and
`71.6741 / 71.5488 tok/s`. Its accepted overlay is the model and launch
identity, XPU graph and oneCCL settings, topology, cache policy, quality suite,
and versioned autotune decisions. There is no hidden source patch to lose in
that lane.

Protected target-only identities include:

- pinned-image diagnostic TP1: `30.2178 / 30.2569`;
- pinned-image diagnostic TP2: `48.8301 / 48.950458800865434`;
- pinned-image diagnostic TP4: `71.6741 / 71.5488`;
- pinned-image strict TP1/TP2: `30.31067504052998 / 49.01965141150585`;
- pinned-image strict TP4 repeat floor/high bar:
  `71.29326283364946 / 71.39843006187554`;
- `a3561ef8` stock diagnostic TP1/TP2/TP4:
  `30.329809361830037 / 48.64759224153825 / 71.34404937397696`;
- `a3561ef8` stock strict TP1 `30.241645123711923 / 30.243714296955797`,
  TP2 `48.49048978038331`, and TP4
  `71.9001988117144 / 71.2457420049019`;
- `a3561ef8` TP2 decision-overlay strict `49.00935245117815`;
- `a3561ef8` TP2 decision-overlay diagnostic `49.05894025767351`;
- `a3561ef8` TP4 decision-overlay diagnostic `71.72254506718171` and strict
  `71.35287190161719 / 71.45427094575045`.

The accepted TP4 decision bundle contains 152 `.best_config` files. The TP2
bundle contains 78 decisions but remains a quality-clean near-recovery rather
than a promoted win. Generated binaries and old outer caches are not portable
overlays; decision files must be remapped and freshly compiled on each base.

The July native-MTP `95.384867741895 tok/s` record is a separate coupled
selection-12, short-context identity. Its vLLM head plus dirty patch, kernel
head plus dirty patch, staged FA changes, oneCCL build, model pair, graph
layout, and launch environment form one historical packet. Individual private
commits are not independently accepted. Its exact preservation identity is:

- source manifest
  `patches/qwen36-27b-autoround-int4-b70/record-20260711/source-manifest.json`
  (SHA-256
  `1a21c604fab3b6cace45f499b410b2e96ae784f9f04b1c67ea9a858c30ce35c2`)
  and packet checksum file beside it;
- vLLM public prerequisite
  `c51df43005726a09c6eb7348e8c1b00501c70a8e`, recorded head
  `e7213ba8e13b74d7bfa3cbc05435a45df90eb76a`, commit bundle SHA-256
  `672b86f07952e93a7d103beefce3ddd93f8a4d58613e710830e75e8331ab12fc`,
  and working-patch SHA-256
  `dcf84454f64bdeca546aa1697f4cd6af89fa95bb56f80ed314ad4d364e134b24`;
- XPU-kernel public prerequisite
  `28e1f5e74c15744b69cf3b760f6160ceabd15de0`, recorded head
  `3b4effeeffd83f6ef4696bbe7e76d924a0e9d171`, commit bundle SHA-256
  `28280d89fb7a3b62565602dd0e074be4ee1911d748c64a8cc580a2e6def565bb`,
  and working-patch SHA-256
  `edcb9314b43d6990474dfb5d64e3716e8d4c33618ec0e3fbd11ae671e47c8c1f`;
- graph-safe FA companion patches
  `experiments/qwen27_graphsafe_flash_attention/qwen27-chunk-prefill-local-accessor.patch`
  (`1f1a016bbf9cd4a71a47657846143913d879424fce73a9f669f982bcdaad165e`),
  `qwen27-chunk-prefill-completion-barrier.patch`
  (`1c2a25bbed856f1e739cb69bc5070b5dd071e38cedb1ccb0cfb21308bbcd17b8`),
  `qwen27-force-chunk-decode.patch`
  (`383730d64b9bc818a56116ab15c2fecca9ab2a00709e08791572244708521a2a`),
  and `qwen27-force-chunk-decode-python.patch`
  (`7fc9847e43e4f4263bfc9c268d9a9c9c834f52bde138af56b7ffb0e07dc5242c`);
- runtime manifest
  `repro/qwen36-27b-autoround-int4-b70/manifests/runtime.json`, including
  oneCCL top commit `b52f40c07f0b140e6aba87548c80720a350a9827`, libccl commit
  `4ceafd15c03ce46f11eeaf91781a92afebd3cecf`, libccl SHA-256
  `43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700`,
  and kernels-SPV SHA-256
  `0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9`.

The later Qwen3.8 `101.17 tok/s` all-25 result must always be shown beside its
suite identity and remains unpromotable while dose-8 graph corruption is open.

## Frozen legacy trees and external recovery

`/home/steve/src/vllm` is clean at `44fc8fde09fc311d3099dab10366b672d9142ea4`
but is 16,942 commits ahead of and 2,468 behind its configured upstream. It is
a divergent research archive, not a rebase candidate.

`/home/steve/src/vllm-xpu-kernels` is clean in tracked content at detached
`2dd55f380df753a10a88fcd9e96192561066e713`; nested oneDNN is clean at
`80afa71049cd69a3df32adcccb623b12cd7baa22`.

The external recovery point is:

`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/`

It contains complete Git bundles plus a 61,869-entry archive of the kernel
`build/`, `install/`, `third_party/`, and complete runtime package. Bundle
verification, `zstd -t`, a complete tar traversal, and per-file hashing passed.
The authoritative artifact hashes are recorded in that directory's
`MANIFEST.md`; the structured overlay companion is
`experiments/qwen38-27b-b70/data/2026-08-23-qwen38-current-main-overlay-manifest.json`
in this repository.

After verification, only the archived ignored `build/` tree (13 GB) and 109
archived backup DSOs (10,458,754,872 bytes) were removed locally. Ten active
DSOs, both source histories, refs, stashes, `install/`, and `third_party/`
remain. Root free space increased from about 2 GB to 25 GB. All removed files
are recoverable from the verified external archive.

## Source classification

### Start from upstream

Current upstream already has native Qwen GDN MTP, split convolution/delta
speculation, the August GDN bounds and work-around fences, and the eager graph
break. Do not duplicate those changes. The old GDN file moved to
`mamba/gdn/qwen_gdn_linear_attn.py`, tree attention was removed, runner
responsibilities split, and the private `spec_decode.hpp` path no longer
exists. The old 33-file patch therefore cannot be applied as text.

Current FA also has a newer small-uniform speculative route controlled by
`VLLM_XPU_SPEC_DECODE_MAX_QLEN` (default 16). Test that route first. Use
`VLLM_XPU_SPEC_DECODE_MAX_QLEN=1` only as an attribution sentinel. Adapt the
old local-accessor/completion-barrier behavior only if a current graph oracle
proves the upstream route still needs it; forced chunk decode remains a
short-context fallback, not a long-context default.

### Accepted only as coupled historical behavior

- July record packet under
  `patches/qwen36-27b-autoround-int4-b70/record-20260711/`;
- target INT8 LM-head behavior with BF16 scales;
- draft INT4 group-128 head behavior with BF16 scales;
- accepted-state promotion/pending metadata/direct output transaction, only if
  current upstream behavior fails a matched oracle;
- compiled all-gather and pinned oneCCL behavior, only if current collectives
  fail on the current runtime.

### Accepted performance inside an optional, token-changing policy

The bounded near-tie sampler base
`c6dc1a3f6d56729d3bde5544420690be9416c5fd` intentionally changes tokens.
Within that policy only,
`011713d34be01018de8f845242807b0937fb8896` and
`44fc8fde09fc311d3099dab10366b672d9142ea4` are accepted speed improvements
(+2.7 tok/s in their matched A/B). The exact closeout packet is
`patches/qwen36-27b-autoround-int4-b70/determinism-closeout-20260818/`:
prerequisite `95a76ff89173ff56e90a2ed384fde2cea3c015e6`, bundle SHA-256
`eb565490b7875d63d91c9e26b4cc1c817b469fca57efdeb62b3177eb9f77fed3`,
and flat-patch SHA-256
`638545d9d548cd42a2674b43eedcb5c1328c678e3a971129ccac3cba45e375d0`.
Qwen3.8 changed 18/25 prompts with the margin enabled, so the policy remains
default-off and is ported last, if at all.

### Historical safety provenance already represented in current upstream

The legacy kernel line contains the ordered safety commits
`3637764dbdf4e1846f1f83f35a58bb3dd3156369` (Xe2 GDN SLM-refill fence),
`add17867ce19b8e3eaa39c2a37f59b6e1a556aa7` (GDN virtual-head bounds), and
`6aed46a4f7ccf6db47323fe9e8eeed243b0ad3d8` (Qwen GDN convolution bounds).
At observed kernel head `4543b580fecca68a7dd54ddaf6e444dc5f11a6a4`,
their public upstream equivalents are respectively
`c9989668e7f280747680def85d58d116126c2249`,
`18b78776ad897daef8b5aeb16bfb919307d97ce4`, and
`5813d7486fb7516adc005732d669cdaa48622c61`. The current-source locations are
`csrc/xpu/gdn_attn/xe_2/chunk_gated_delta_rule_kernels_xe2.hpp` (SLM fences
and virtual-head bounds) and `csrc/xpu/gdn_attn/causal_conv1d.hpp` plus
`xe_2/chunk_causal_conv1d_xe2.hpp` (convolution bounds). Preserve the legacy
hashes as provenance and prove the behavior with current-source oracles; do
not cherry-pick the old commits merely because their hashes are not ancestors
of upstream `main`.

The later zero-initialization commit is preserved as WIP with an insufficient
result, not as an accepted or diagnostic-only port. Commit
`0ab8205756b52082399ae1849c0cfb6915f63f04` is not a sufficient corruption
fix. Its preserved patch is
`experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-scratch-zero-init-20260818.patch`
(SHA-256
`45791a28c8ef609368ab84fbc3d20be00759841df49c2760a7c35e9573244d5b`).
It zeroes the persistent buffers but does not identify the read-before-write
site, and the dose-8 multi-chunk program still proved persistent scratch
unsafe. Do not port it until the mechanism is fixed, and never enable it by
default merely because it exists.

### Excluded from the default port

- persistent graph scratch
  `534bd9ccca74e0b076067a212271f896bb137d2a`: unsafe; dose-8 multi-chunk
  corruption;
- per-layer scratch isolation
  `4050008863bf0db6047935f775378ab882265300`: did not fix corruption;
- explicit INT4 dependency
  `2f18699b7f99fb8748f2dc56679925c847bee8f9`: correctness-only,
  performance-neutral, and probed only if the current dependency oracle fails;
- in-place all-reduce `1dbb48599c55de3be8dc74e0cbdfc831d9481e06`:
  correctness-only and performance-rejected at `80.859 tok/s`;
- batch-stable RMS, margin-acceptance, serialization/dependency,
  cross-config-invariance, and qk-RMS stacks: rejected or failed;
- D1/D2, poison, GDN factorial, serial-recurrence, and source-state traces:
  diagnostic only;
- `mtp.fc` INT4 patch SHA-256
  `95fca14c87dabbec6de40f2089985880fa2a604a47d4796123a3254eb5a0a49c`:
  quality-clean but rate-neutral/slightly negative, default-off;
- replay-bypass/margin stash: failed diagnostic WIP, preserved but never ported.

### Qualified candidates, not accepted defaults

- Q64xK32 r2: operator-qualified and short-KV positive, but long-context value
  is blocked by corruption;
- draft top-K rerank;
- oneDNN INT4 padding (scoped TP1 causal positive only);
- MTP4 serial-exact and packed-GDN ordinary-shape experiments;
- ReplaySSM commit-race fix, mandatory only if ReplaySSM is deliberately
  revived.

The structured manifest keys the exact artifact path, SHA-256, classification,
result status, default state, evidence, and current-main disposition for every
source delta above. It also preserves the legacy correctness chain at commits
`ad765a733ab5749abee1b3f0058ad78c7401fe18`,
`d07ee87a939d7a1f0e2a548207ef4c014f524d6d`,
`50e729b1e87559eef8709c9836195f50766ba791`,
`9bcc0cb9429683fbc84011332c0a3acd698ab8dd`, and
`2dd55f380df753a10a88fcd9e96192561066e713`. Those behaviors receive semantic
oracles before any selective port; their presence in the archive is not a
reason to copy obsolete text.

## Ordered current-main qualification

1. Create fresh single-branch `main` integration trees at freshly resolved
   upstream vLLM and kernel heads. Never mutate or rebase the archives.
2. Build a zero-lab-overlay control on the official nightly runtime base.
3. Prove model identity, eager native MTP, and target-only service at TP1, then
   TP2, then TP4. Each topology receives a fresh ext4 cache.
4. Reapply the target-only config overlay and remap autotune decisions. Require
   cache-zero canaries, exact token accounting, quality/baseline/needle gates,
   immutable replay, and protected performance floors before promotion.
5. Test graph+MTP with the current small-uniform FA route on/off. Fix graph
   correctness before any speed port.
6. Port target INT8 and draft INT4 head behaviors separately, each with
   loader/operator/TP1/TP2/TP4 receipts.
7. Use current collectives and native GDN transaction first. Port older
   behavior only when a matched oracle proves it is still required.
8. Keep persistent scratch off until dose-8 corruption is actually fixed.
9. Run active-depth context gates at 0/2K/4K/8K/16K/24K/32K and record decode,
   prefill, TTFT, VRAM, quality, and uncertainty.
10. Publish each exact base/overlay identity as a separate neural.download
    profile. Fill lower-value gaps with versioned estimates rather than
    inheriting conclusions across bases.

The TP4 promotion rule remains conjunctive: both strict repeats must clear
`71.29326283364946`, and at least one must clear `71.39843006187554`. A moved
base that misses a gate remains evidence; it cannot lower or replace the
historical frontier.

## Packet-integrity correction

The preservation gate exposed one stale checksum in the July repro packet.
`download-model.sh` intentionally gained `MODEL_MANIFEST` support when the
Qwen3.8 lane opened, but `repro/.../SHA256SUMS` still contained the prior file
hash. The ledger was updated to the tracked script's SHA-256
`45b4de5ef716585845379a7772bb903617306c1b374ed044c4388a9d6efa0840`.
The complete repro verifier and both source/determinism packet checksum sets
then passed.

## 2026-08-24 literal-head refresh

The first preregistered TP1 campaign stopped before creating a container when
vLLM `main` advanced during its launch preflight. That was the intended
fail-closed result: no GPU work ran and the `2ec6f0d71e` images remained dated
artifacts rather than being relabeled as current.

The source tree was then fast-forwarded and both zero-source-overlay images
were rebuilt at literal vLLM head
`e8888b2d68bd7c6cce0aada7f0e214e55020e20d`, tree
`8f15832ef5a8912e4f4531b40730648b2c4806ea`, with XPU-kernel head
`4543b580fecca68a7dd54ddaf6e444dc5f11a6a4`. The vLLM delta from
`2ec6f0d71e` is one direct-parent commit limited to ModernBERT FP8 support and
its tests. Exact Git-object comparisons found the Qwen3.5/3.8, INC/AutoRound,
XPU graph, scheduler, cache, LM-head, GDN, collective, and TP paths unchanged.
This predicts no Qwen semantic or performance change, but does not waive
requalification.

The current immutable image IDs are:

- current vLLM with stock-base kernel:
  `sha256:84c1cb317728428107eedaaac10289b39cdeb9268d3965e332d4193e5ed55ca4`;
- current vLLM with current official kernel artifact:
  `sha256:f9887e6270c47dff470cff1c927c4baa22cdb1b128ff42c945a57a7717c04537`.

Their complete build archive is
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T030607Z-e8888b2d68-4543b580fe`.
The tracked receipt, build-root receipt, and archived receipt are byte-identical
at SHA-256
`459d32899d0a53d0868fdb33ab0934dbff7c38f0a7f5efcac31c651ad0d301b9`,
and the full archive checksum manifest passes. The builder's original receipt
is retained beside it as `build-receipt.pre-finalization.json`; finalization
added only image IDs and static-preflight hashes derived from its saved image
inspections and preflight outputs.

The floating official `vllm/vllm-openai-xpu:nightly` registry index was
re-resolved immediately after the build and still matched pinned digest
`sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`.
The builder and qualification runners now check that live digest before and
after their work, alongside both Git heads, so a moved runtime base also makes
an otherwise successful result stale before promotion. Future builder receipts
capture immutable image IDs and static-preflight hashes directly. No launch
flags, protected floors, accepted decision overlays, or historical result
values changed in this refresh.

Only unused Docker build cache was pruned after the archive passed. The local
e888 images were later removed when a newer vLLM head required another build;
their verified USB build archive, retained local source tar, pinned inputs, and
all run/result evidence remain, so the dated runtime can be reconstructed from
exact pinned inputs. The literal image IDs were not exported, and BuildKit
provenance attestations can change a rebuilt manifest-list ID. GPU qualification
is still pending and the historical TP1/TP2/TP4 highs remain authoritative
until a newer identity clears every speed and quality gate.

The first e888 GPU attempt is preserved at
`/home/steve/qwen38-current-main-runs/tp1-20260824T031808Z`. Its control arm
verified all model files, loaded the model, compiled the fresh graph cache, and
became healthy, then stopped before sending any benchmark or quality request.
The report-only stack-version probe incorrectly required
`/workspace/vllm` itself to be absent. The derived image correctly imports
vLLM from site-packages, but the inherited base workdir was recreated as an
empty, ordinary directory during later image-build steps. Thus the failure is
a harness false negative, not a speed or model-correctness result; it produced
no decode measurement and changes no protected value.

The qualification gate now accepts only two safe states for that legacy path:
absent, or a non-symlink directory with no entries. It still requires the
resolved import to live under the exact site-packages directory. Both sealed
images passed that corrected gate without a GPU. For future images, the
Dockerfile switches to `/workspace/runtime` before removing the base source
tree so build steps do not recreate the empty legacy workdir. This harness and
future-build correction changes no launch argument, runtime package, graph
setting, or performance overlay on the already sealed e888 images.

The corrected rerun at
`/home/steve/qwen38-current-main-runs/tp1-20260824T032648Z` produced a valid
25-row control diagnostic before a second bookkeeping-only campaign stop. Its
conventional 1--100 interval median is `30.351516250263348 tok/s`, above the
protected `30.2178` diagnostic floor; canary, model identity, cache-zero
request shape, and all three upstream-recency checks passed. This is a valid
diagnostic measurement, but it is not a completed TP1 qualification and does
not replace the historical result.

After the arm wrote a hash-only cache-manifest digest and `final.status=pass`,
the unconditional EXIT cleanup recomputed the same manifest but overwrote the
digest file with standard `sha256sum` output containing both hash and path.
The parent expected exactly 64 hexadecimal characters and stopped before
strict replay. The digest content was normalized back to its verified hash
`0a6ab96e888b78e07b0651cd166e60be55ac70867ec00099ad0e6830372ac17c`.
Cleanup now writes the same hash-only format as the normal path, and the parent
independently recomputes and compares the digest before replay. No strict or
quality arm ran in this attempt; the completed diagnostic and cache remain
preserved as extra replication evidence.

The next clean campaign at
`/home/steve/qwen38-current-main-runs/tp1-20260824T034038Z` passed the digest
handoff and entered replay. Its control diagnostic measured
`30.421310780232716 tok/s`; strict replay A measured
`30.320453612816877 tok/s`, narrowly above the protected
`30.31067504052998` strict floor. Strict A also passed the complete quality
and baseline battery: seven exact cases, eight repeats, the 8K/7617-token
needle, 24 baseline comparisons, and zero cached tokens throughout. The
1,097-file diagnostic cache manifest was byte-identical before and after
replay.

That arm is still not promotable. vLLM `main` was `e8888b2d68` at its
preflight and advanced to `702e1d7186` before its postflight; the kernel and
nightly runtime digest did not move. The runner therefore wrote
`stale-before-promotion` and stopped before strict B or either both-current
arm. The exact partial-attempt ledger is
`experiments/qwen38-27b-b70/data/2026-08-24-qwen38-e888-tp1-qualification-attempts.json`.
These are useful dated speed/quality/cache results and cannot be discarded,
but recency remains a conjunctive gate: rebuild from the new head and restart
qualification without changing the accepted overlay or historical floors.

## 2026-08-24 `702e1d718` forward sync

The replacement zero-source-overlay build uses literal vLLM head
`702e1d718646b5290f17533c04932d58bf03dad6`, tree
`3ebf6c94f19ab1e4a41f83baf5fc1812c4fe9f03`, and the unchanged official XPU
kernel head `4543b580fecca68a7dd54ddaf6e444dc5f11a6a4`. The single-commit delta from
`e8888b2d68` adds LoRA support for DeepSeek V4. Its three changed Python files
do not touch Qwen, INC/AutoRound, GDN, XPU graphs, scheduling, caches,
collectives, tensor parallelism, kernels, Rust, dependencies, or build
configuration. The one shared routed-expert mapping is behaviorally unchanged
when LoRA prefixes are empty; this dense Qwen lane does not enable LoRA. That
is a low-risk source audit, not a substitute for speed and quality replay.

The builder produced vLLM wheel SHA-256
`f82f780fd9b8111eb4f4c0bbdd0aa5e72ec45ef012547bf0b529537d3671a4d0`
and two immutable images:

- current vLLM with stock-base kernel:
  `sha256:d7372613500de2c823becd2364b322b7d7f7827b6fd0705500b14328f1eacdda`;
- current vLLM with current official kernel artifact:
  `sha256:eaa0f2c7a2ea5db677945d29e664f105e38a661446caea9d3e212fd0e118ff0a`.

Their complete archive is
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T040536Z-702e1d7186-4543b580fe`.
The tracked and archived receipts are byte-identical at SHA-256
`22d5577b3054e6c1ed5a82dbd94594f408085888d50832be562dd9b4c21e00a5`,
and the archive checksum manifest passes. Both images passed package, import,
source-shadowing, DSO, dependency, kernel, and static identity checks. A
post-build re-resolution found vLLM main, kernel main, and the official nightly
index digest still unchanged at the identities above and
`sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`.
An independent live recheck sealed those three identities at
`2026-08-24T04:11:20Z`.

After sealing the archive, 8.038 GB of unused and reproducible Docker build
cache was removed. The two `702e1d718` images, exact wheel/source archive,
receipts, run data, accepted overlay artifacts, and historical evidence remain.
No protected floor, launch flag, quality gate, decision overlay, or historical
speed value changed. Full TP1 qualification is still required before TP2/TP4.

## 2026-08-24 kernel-head advance during TP1

The clean six-arm campaign at
`/home/steve/qwen38-current-main-runs/tp1-20260824T041736Z` completed its
current-vLLM/stock-kernel fresh diagnostic, then stopped at the arm postflight
because XPU-kernel `main` advanced from `4543b580fe` to `baaa05bb4e`. vLLM
remained `702e1d7186` and the official nightly index remained
`sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`.
The recency veto was the only stop reason.

The completed diagnostic is valid dated evidence. Its preferred conventional
99-interval median is `30.3357425320144 tok/s`, clearing the protected
`30.2178` diagnostic floor by `0.1179425320144 tok/s`. All 25 unique prompts
returned 512 token IDs, every request reported zero cached tokens, code-14 and
the direct-plus-ordinary 19-file model verifier passed, and the post-container
1,097-entry cache manifest was sealed at
`9a11b2781613e890d0ebe810fc861a43a62617cd1622ca1a970b170c3862d37a`.
Strict A/B and all three both-current arms did not run, so this is neither a
complete TP1 qualification nor kernel attribution. The structured evidence is
`experiments/qwen38-27b-b70/data/2026-08-24-qwen38-702-tp1-qualification-attempts.json`.

The kernel delta is one direct-parent commit with 18 added lines in
`fp8_gemm_w8a16.h` and `fp8_gemm_w8a8.h`. It adds host-side divisibility
checks for block-FP8 scale grids. The target model is AutoRound INT4 W4A16;
its MTP, graph, GDN, FlashAttention, collective, autotune, and TP paths do not
use either changed header, and no accepted overlay touches them. Expected Qwen
performance and semantics are unchanged, but exact-current qualification still
requires the new kernel DSO/image and a complete replay.

At the stop boundary, upstream CI had not yet published a successful
wheel-per-commit full-config artifact for `baaa05bb4e`. A default-config wheel
was available but is not provenance/config equivalent and must not be used.
The `702e1d718`/`4543b580` images are now dated artifacts. Wait for the exact
full artifact—or follow a still-newer head if `main` advances again—then rebuild
without weakening launch settings, quality gates, accepted overlays, or
historical floors.

## 2026-08-24 literal-current `460c08bc8` / `baaa05bb4e` rebuild

The next fail-closed update followed all three moving inputs to their literal
live identities before and after the build:

- vLLM `460c08bc8a525082f37b1ba4c8e70558e5aa8e9e`, tree
  `1bf1f2c8e421688aba1c51882acc0d323d2e0f87`;
- vLLM XPU kernels `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`;
- official XPU nightly index
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`,
  whose embedded vLLM is `f94666b60d4c58ec0807d22c837cfae322a1dde9`
  and stock kernel is `0.1.13.2`.

The source delta after `702e1d718` is bounded but not waved through. Commit
`f94666b60` skips the oneCCL warm-up all-reduce only at world size one, before
model loading and decode. Commit `e6e1af4ca` tunes CUDA/FlashInfer all-reduce
selection, and `460c08bc8` adds Qwen3-Omni multimodal LoRA support. The latter
two do not enter this dense Qwen XPU path. Kernel commit `baaa05bb4e` adds only
host-side block-FP8 scale-grid divisibility checks; the protected target is
AutoRound INT4 W4A16. These audits predict no steady-state loss, but TP1/2/4
performance and quality replay remain mandatory.

The current kernel came from successful full-config unit-test run
`32689598992` and wheel-per-commit run `32692290527`, artifact `9508328924`.
The artifact archive digest is
`sha256:ce94da86eb14e61673a10db5c8a2c3fffb49a5f61ec9d36c210601062f887f10`;
the exact wheel SHA-256 is
`7b886fa814469aef8904118729f31f2fe77559f3c5219bd0ecf799a904387483`.
Its `build_info.txt`, package version `0.1.dev1+gbaaa05bb4`, full DSO member
set, workflow, and full attention-config hashes all passed. The upstream
artifact-name short SHA is blank because of an upstream metadata-output bug;
the full commit field, run head, and wheel version independently agree.

The builder produced vLLM wheel SHA-256
`415aedb71c0f5db997768a9244455d8d72cd198f77a9cc2f8a022122016a9446`
and two immutable images:

- current vLLM with the new nightly's stock kernel:
  `sha256:b4451bcd0dbb1fe79fd46ce0cd6adc02b2f57a1ce0c4af0a436553514045fd5a`;
- current vLLM with the exact current kernel artifact:
  `sha256:6ea7380f8990a3df97e4699a1571727ec68d0bdacb0a4fbd512301ecefa64df9`.

The complete archive is
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T054447Z-460c08bc8a-baaa05bb4e`.
Its checksum manifest passes. The tracked receipt is byte-identical to the
archived receipt at SHA-256
`1e383c644ce4fcf393978fa0c88bb84461fd7a2f67437b82a7da8bdc513f006c`.
Both images passed package, import, source-shadowing, DSO, dependency, kernel,
and static identity checks, followed by a live post-build source/base seal.

To preserve enough ext4 space for qualification, the already archived and
superseded `702e1d718` control/current-kernel images and the old digest-pinned
base were removed locally, followed by reproducible inactive BuildKit cache.
Four completed build scratch trees (`2ec6f0d71e`, `e8888b2d68`, `702e1d7186`,
and `460c08bc8a`) were also removed only after each matching versioned archive
passed its full `SHA256SUMS`; the separate incomplete `2ec6f0d71e` attempt was
left untouched for later classification.
The dated `702` run evidence, wheel/source archive, receipts, logs, and every
accepted decision/source overlay remain. No historical speed or quality value
was replaced. The new images are still unqualified; full TP1 diagnostic plus
strict A/B must pass before separate TP2 and TP4 overlay remapping begins.

## 2026-08-24 `460c08bc8` diagnostic and `8c2bbe00d` roll-forward

The `460c08bc8` control diagnostic completed before promotion was vetoed by
the per-arm recency gate. Its 25-prompt conventional 99-interval median was
`30.333869114906538 tok/s`, `0.11606911490653715 tok/s` above the protected
diagnostic floor. The canary, returned-token accounting, zero-cache checks,
direct-plus-ordinary 19-file model verification, and 1,097-file cache seal all
passed. It was not a strict arm: natural-EOS quality, strict replay A/B, and
both-current were never run. It therefore remains valid dated diagnostic
evidence and does not replace a strict result or any historical high.

The exact reason for the stop was vLLM `main` advancing from
`460c08bc8a525082f37b1ba4c8e70558e5aa8e9e` to
`8c2bbe00d58a930c6c09a80495728b26b79d9200`. The kernel head and official
nightly digest did not change. Structured evidence is in
`experiments/qwen38-27b-b70/data/2026-08-24-qwen38-460c-tp1-qualification-attempts.json`.
The complete raw run is independently archived at
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/tp1-20260824T055200Z-460c08bc8a-stale-diagnostic.tar.zst`,
SHA-256
`c5db478ceb7df910b7996ce669eeb2e6e103b7d4416aaece8c5c7121067ed817`.

The new vLLM commit adds only Muse-Glimmer multimodal LoRA module mapping;
it does not enter the protected Qwen/XPU path. That bounded audit does not
waive qualification. Literal live identities were resolved again, and the
unchanged exact kernel artifact and nightly base were reused only after the
Rust-equivalence, artifact, import, dependency, DSO, and source-identity gates
passed. The new vLLM wheel SHA-256 is
`7fd324aa008dae05e97e75c06454d665b7fb6e0c15d4bae71368e2968e7966ef`.

The rebuilt immutable image IDs are:

- current vLLM with stock nightly kernel:
  `sha256:83aaedca61fb3c55e4303ef8b2ab72744e16e0b3e9e61844e3298deb45354842`;
- current vLLM with exact `baaa05bb4e` kernel:
  `sha256:bee7e67a41a15cbe05fa9ddbeeaca659b8a4a01498609c053fdfb34a73bc0637`.

Their verified archive is
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T060421Z-8c2bbe00d5-baaa05bb4e`.
The tracked and archived receipts are byte-identical at SHA-256
`49f85b12d2affd9700e6bf82cda1c60ce0b720b4f44cb2a82985cd21347d1223`.
Historical build entries now point at immutable archived receipts rather than
the mutable current-receipt path. The Dockerfile no longer supplies a stale
fallback base to manual builds, and campaign cleanup now propagates the
semantic `stale-before-promotion` arm status instead of hiding it as a generic
exit code.

No source performance overlay was dropped. The current build remains a
zero-source-overlay attribution base; the accepted launch, topology, graph,
autotune-decision, cache, and quality overlays remain versioned and await
exact-path/config-hash remapping after TP1. The protected TP1/TP2/TP4 speed
history is unchanged and append-only.

## 2026-08-24 `a4d70bef3` literal-current roll-forward

The prelaunch recency gate stopped the unrun `8c2bbe00d` candidate when vLLM
`main` advanced by one commit to
`a4d70bef3724edb068c8206804154065acaa4cd4` (tree
`7a53aac59000b1dfd47c8a8948486ff9f3f2c228`). No `8c2bbe00d` GPU arm was
launched. Its exact receipt, wheel, source archive, build logs, and image
identities remain dated evidence in
`current-main-builds/20260824T060421Z-8c2bbe00d5-baaa05bb4e/`; the late-copied
source tar is anchored by receipt SHA-256
`7110d72bcf7fc2e07196af7e9f4cf4440bf62527ca13ebcf65e1db71f8f495e7`
rather than being silently represented as an original `SHA256SUMS` member.

The single upstream delta, `[Model Runner V2] Reserve CUDA graph memory`, is
scoped to CUDA/ROCm Model Runner V2 profiling. Existing captured evidence
resolves this Qwen lane as `Qwen3_5ForConditionalGeneration` on the V1 engine,
with no `VLLM_USE_V2_MODEL_RUNNER`; the active XPU V1 runner, XPU GDN, graph,
quantization, collective, and kernel paths are unchanged. This bounded audit
predicts no steady-state change but does not waive fresh performance or quality
qualification.

The exact a4d build has:

- vLLM wheel SHA-256
  `48495720ed29ec11c39538a3e94bcc5ab8985b74249a0424535c3aecba902467`;
- vLLM source-tar SHA-256
  `c9ba8e4d2e4d7848a23a7dc7dbdc9dc8e02f1f64746183bab1dca37b98bf9149`;
- current-vLLM/stock-kernel image
  `sha256:58f96e00d65123179f6bb0a6bebc21de8bb5e19295f2f478fa30b3103fce4780`;
- current-vLLM/exact-`baaa05bb4e`-kernel image
  `sha256:4718fdd224aae9ea95bfbd7bc5aea7eea64ddc51975e2d8d09fa6fdcf5efd0cf`.

Its archive is
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T062226Z-a4d70bef37-baaa05bb4e`.
The tracked and archived receipts are byte-identical at SHA-256
`473f7bf9f7a00d00dfabb6214a57d7bed6beeb94cc479cfee5fa3293c93f91d2`.
The source tar was added to the archive manifest explicitly, all archive hashes
pass, and its 7,581-entry traversal is safe. A live `--validate-only` seal at
`2026-08-24T06:27:16Z` confirmed the same vLLM head, kernel head, nightly base,
and official kernel wheel.

The completed but stale `460c08bc8` measured control image is additionally
preserved as a runnable Docker-load archive at
`current-main-builds/20260824T054447Z-460c08bc8a-baaa05bb4e/control-image-b4451bcd0dbb.docker.tar.zst`,
SHA-256
`77252e0564fb2fcadcb48a24230616b27dbbf9c3e29cb072841a2b5161a5a3af`.
It is a Docker archive of the measured platform image, not a claim that the
original Buildx index/attestation digest was reconstructed.

After these archives passed, only superseded unqualified local images and
inactive reproducible BuildKit cache were removed. At that point the a4d images, the
official base, all results and source packets, the 78-file TP2 decision bundle,
and the accepted 152-file TP4 decision bundle remain intact. Root free space
returned above the launch safety floor. The TP2/TP4 decision overlays are not
implicitly portable through their old a356-bound runners: they require explicit
current-image path/config-hash remapping and fresh compilation before claiming
that the performance overlay has been carried forward.

## 2026-08-24 `a4d70bef3` hash-seed-unset diagnostic

The preregistered both-current TP1 diagnostic with `PYTHONHASHSEED` truly
absent completed its full 25-prompt benchmark at
`30.25330610145591 tok/s` on the conventional 99-interval metric. That is
`0.03550610145590838 tok/s` above the protected `30.2178` diagnostic floor
and only `0.003593898544092866 tok/s` below the protected `30.2569` captured
high. The high remains append-only and is not replaced. This was an
ignore-EOS diagnostic, not a strict or quality-battery arm.

The benchmark, code-14 canary, returned-token and zero-cache accounting,
GPU-0 BDF/UUID mapping, and direct-plus-ordinary verification of all 19 model
files passed. The fresh cache contains 1,097 files, including 38 autotune
decision files. It has a verified post-run seal, but no replay occurred, so it
does not establish fresh-compile determinism and none of its AOT models,
binaries, or generated kernels may be reused on another code identity.

Promotion was correctly vetoed after the valid benchmark because vLLM `main`
advanced from `a4d70bef3724edb068c8206804154065acaa4cd4` to
`cc40c3673b47a58d1326d1e7a2798f1f67a94a8f` during the arm. The kernel head
and official nightly digest remained unchanged. Structured evidence is in
`experiments/qwen38-27b-b70/data/2026-08-24-qwen38-a4d-hash-unset-tp1-diagnostic-attempt.json`.
The complete 1,358-entry run, including its cache, is archived at
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/tp1-hash-unset-20260824T064134Z-a4d70bef37-stale-diagnostic.tar.zst`,
SHA-256
`d62187e66a3da0d5fe294f686fd01c2582f0eda7f08f0f2d34aaa98a4e277453`.

The wrapper formerly summarized this specific inner recency veto as generic
`fail rc=5`; the inner arm already recorded `stale-before-promotion`. Future
runs now propagate that semantic status at the wrapper root. The build receipt
also now exposes the already-verified Rust reuse hashes at top level so a
consumer cannot mistake an omitted field for missing provenance.

No accepted optimization was abandoned. This evidence confirms the protected
runtime overlay still delivers the historical TP1 speed class on `a4d`; the
next literal-current build must use a fresh compile cache, repeat this gate,
then run strict/quality qualification. TP2's 78 and TP4's accepted 152
`.best_config` files remain immutable decision-only overlays awaiting exact
relative-path plus embedded-`configs_hash` remapping on that new base.

## 2026-08-24 `a047e2543` literal-current build

Upstream continued from the stale observation through `cc40c3673` and
`26858770e` to `a047e2543da570a64d1bbfeac4fe44eff3e87a81` (tree
`2c2bce17a3e5897184edfa66e26715965a1e9f22`). The cumulative three-commit
delta from a4d is one CPU documentation update, CUDA/NCCL packed-weight
transfer stream reuse, and a CUDA SM90+/MNNVL Lamport-mailbox fix. Qwen3.5,
MTP, INC, XPU platform, V1, compilation, packaging, requirements, and Rust
inputs are byte-identical. The CUDA header is excluded by the XPU CMake path,
and the optional NCCL weight-transfer module is not configured in this lane.
That audit predicts no Qwen/XPU speed change but does not waive qualification.

The new exact build has:

- package `0.26.1rc1.dev1140+ga047e2543.xpu`;
- vLLM wheel SHA-256
  `7673a25c5308a88bff3d8186533892a39e3ea3f381f735b62d04dc7f3399ff2c`;
- vLLM source-tar SHA-256
  `98abf2d746cb4515b4e5c74429867edbd064a20ef41c182814be837952fe026f`;
- current-vLLM/stock-kernel image
  `sha256:4ca9cb9063ddd662e8cdd3f2901bab31d67ea71bba3e0f3611e12039f444ba72`;
- current-vLLM/exact-`baaa05bb4e`-kernel image
  `sha256:a63ed5c5e19b639813ba47e94e13fb739c3467ef74cc8ba4beaa9d99a5e6241c`.

The tracked and archived build receipts are byte-identical at SHA-256
`4c389b109e36021d4603873d441ac81766e4982be6c204405801303c465b810d`.
Their top-level `reused_rust` object records the verified extension and
frontend hashes instead of requiring readers to infer them from the nested
source receipt. The immutable build archive is
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T070008Z-a047e2543d-baaa05bb4e`.
Its `SHA256SUMS` SHA-256 is
`b420e9c5182271539bb4b27d62705521a0cd91868655750ac13fd70bab34151e`;
all 15 payload hashes pass, and the 7,582-entry source tar is traversal-safe.
A live seal at `2026-08-24T07:04:31Z` still matched the vLLM head, unchanged
kernel head, and official nightly digest.

This remains zero lab source overlay only in the attribution sense. The
accepted performance work is still mandatory and preserved separately:
model/quant identity, launch/topology settings, XPU graph, ext4 fresh-cache
policy, quality and recency gates, plus the TP2 78-file and accepted TP4
152-file decision overlays. The version change deliberately changes outer and
AOT cache namespaces. Therefore the next run compiles fresh; it never imports
a4d AOT models, binaries, or generated kernels, and later remapping may copy
only exact relative-path and embedded-`configs_hash`-compatible decision
bytes before full requalification.

Before removing the now-superseded a4d tags for launch disk headroom, the
exact measured both-current image was exported as a Docker-loadable archive:

`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T062226Z-a4d70bef37-baaa05bb4e/both-current-image-4718fdd224aa.docker.tar.zst`.

Its SHA-256 is
`0597d99fed986aefea19935c208a5c47577be9dfba79827d994ddf7ff94da5c4`;
it is 5,692,633,435 bytes compressed, 5,713,474,048 bytes uncompressed,
contains 38 tar entries, and passed both `zstd -t` and the safe traversal
check. The a4d build archive now has 16 verified payloads and `SHA256SUMS`
SHA-256
`aed44b7203dd9e81c3de2f5ca1e298e0f1752daa1858add6788b7ba70e30d64d`.
Only after that verification were the two superseded local a4d image tags
removed. The current a047 images, official base, every result and patch, and
both decision overlays remain local; the measured a4d image can be loaded
directly from USB, while both a4d lanes are also rebuildable from the exact
preserved source/wheel/base/kernel receipts.

## 2026-08-24 `a047e2543` TP1 diagnostics and preservation

The separate both-current hash-seed-unset arm completed while a047 was still
literal current. Its conventional 99-interval median was
`30.267690888459764 tok/s`, with p10 `30.23479995632769` and mean
`30.311271833920163`. That is `0.04989088845976397 tok/s` above the protected
`30.2178` diagnostic floor and `0.010790888459762726 tok/s` above the older
`30.2569` diagnostic capture. It is appended as a new dated diagnostic point;
it does not replace the older capture and is not strict, natural-EOS, or full
quality-battery qualification.

All 25 unique rows returned 512 token IDs with `cached_tokens=0` and a length
finish. The code-14 canary, exact GPU identity, and direct-plus-ordinary reads
of all 19 model files passed. The fresh cache has 1,097 files and 38
`.best_config` decisions. Its outer compile key is `9903ff08c2`; AOT key
`8b857c7109b855ffd2b215f3eef7492d6c8345e080eba0d3a789faeea036fcac`;
code/config/compiler hashes are respectively
`fb13d4aa1ef8a386c76ab56d39925ff4de083895d9dcbd136e778046e78bb118`,
`93957a4369`, and `ddcad03736`. No replay occurred, so this cache does not
prove determinism and none of its compiled artifacts is portable.

Only 18 of 25 complete token sequences match the preceding a4d fresh compile.
The seven differing zero-based rows are `1, 4, 7, 8, 14, 15, 16`; the earliest
divergence is token index 18. The cross-boot/fresh-compile nondeterminism
disclosure therefore remains mandatory. The complete 1,360-entry run and
cache are archived at
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/tp1-hash-unset-20260824T071159Z-a047e2543d-current-diagnostic.tar.zst`,
SHA-256
`95cdcb82fde92d815e4fd88099ef8b0f2cfde6a84fc8201acf688d65ae731359`.

The frozen seed-zero six-arm campaign then began on a047. Its first
current-vLLM/stock-kernel control diagnostic completed validly at
`30.322439318579008 tok/s` (p10 `30.2721141679398`, mean
`30.357364273568688`) with the same 25-row token/cache shape, canary, and
19-file model verification. This was still an ignore-EOS diagnostic; its
numeric position above the strict floor is not a strict result. The postflight
gate observed vLLM advance to `0ecc284790e5403f74b899524ef82ecb69f83cb3`
and stopped before both strict control replays and all three both-current arms.
The 1,375-entry partial campaign is archived at
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/tp1-20260824T072449Z-a047e2543d-stale-control-diagnostic.tar.zst`,
SHA-256
`14ae21e3c5fc15ef44910088ab44b57afa0a17aa3a423a3f9f53c462247426c7`.
Both a047 attempts are summarized without promotion in
`experiments/qwen38-27b-b70/data/2026-08-24-qwen38-a047-tp1-qualification-attempts.json`.

Before removing the superseded a047 tags, the exact measured both-current
image was exported as a Docker-loadable archive at
`current-main-builds/20260824T070008Z-a047e2543d-baaa05bb4e/both-current-image-a63ed5c5e19b.docker.tar.zst`.
Its SHA-256 is
`25774fb4a2ca9d6868dc3ee1cd26468ff1a76a65636981921f726b5f7c329f32`;
it is 5,692,597,315 bytes compressed and 5,713,474,560 bytes uncompressed,
contains 38 entries, and passed compression and safe-traversal checks. The
a047 build archive now has 16 verified payloads and `SHA256SUMS` SHA-256
`7675ee4b0e6c871c391f3d88635907de5f08d9ca527b89635a2bb6473eb605d8`.
Only after verification were the local a047 control and both-current images
removed. Exact source, wheel, receipt, logs, measured run caches, and a
loadable measured image remain externally recoverable.

## 2026-08-24 `0ecc284790` literal-current roll-forward

The direct a047 child is
`0ecc284790e5403f74b899524ef82ecb69f83cb3` (tree
`942cc5fd4d0ae008499926a1949630f627b87f71`). Its sole upstream commit fixes
Model Runner V2 DCP slot mapping by separating logical and physical kernel KV
block sizes. The exact delta is 73 insertions and 15 deletions in
`vllm/v1/worker/gpu/block_table.py` plus its CUDA test. Qwen3.5/MTP, INC,
XPU platform and legacy runner, graph/compilation/cache framework, packaging,
native sources, and Rust are byte-identical to a047. The changed V2 object and
Triton mapping kernel are not instantiated or compiled in the protected V1,
DCP1 Qwen XPU lane. This predicts no speed change but does not waive fresh
qualification.

The exact zero-source-overlay 0ecc build has:

- package `0.26.1rc1.dev1141+g0ecc28479.xpu`;
- source-tar SHA-256
  `4067d0f3a1b700e23c1f2e7aae73efa725e2cdd8c8dac9341da97add9f8ce6bc`;
- wheel SHA-256
  `12c09824dc11491368046428420c03b0d20dad6d6a86768d71b60d406ea162fc`;
- current-vLLM/stock-kernel image
  `sha256:22a03a3db5ce34419562706d4a95394d67bd788c6d7eb63916ba436927e0845e`;
- current-vLLM/exact-`baaa05bb4e`-kernel image
  `sha256:b44e0658393e5a57f8af7173e9f42c7498763b9b581a57cba0f5ce5b8a597728`.

Its immutable archive is
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T073855Z-0ecc284790-baaa05bb4e`.
The tracked and archived receipts are byte-identical at SHA-256
`275029980b9c1b59b341ca8a2e2ca1d8845505f74e700cc9e653635c1bb96947`.
All 15 payload hashes pass; `SHA256SUMS` has SHA-256
`7f15b12105d3c5617a2c9e59a093567810d79aa9bbf2402812d2f633212b5788`;
the source tar has 7,582 safe entries and independently matches the Git archive
identity. Live checks at `2026-08-24T07:47:18Z` still resolved vLLM 0ecc,
kernel `baaa05bb4e`, and the unchanged official nightly digest.

No accepted optimization was dropped during this fast-forward. The active
source base is fresh upstream, while the protected model/quant identity,
launch/topology/graph settings, quality and recency gates, and the immutable
TP2 78-file and accepted TP4 152-file decision overlays remain explicit.
0ecc must compile fresh. Only exact relative-path and embedded-`configs_hash`
compatible decision bytes may later be remapped, followed by full TP2/TP4
qualification at their original floors. Historical diagnostics and strict
captures remain append-only.

## 2026-08-24 `0ecc284790` TP1 hash-seed-unset diagnostic

The exact-current both-current diagnostic passed at
`30.265258667943765 tok/s` on the conventional 99-interval metric, with p10
`30.173796820876674` and mean `30.29772460691972`. This is
`0.047458667943764965 tok/s` above the protected `30.2178` floor and
`0.00835866794376372 tok/s` above the older `30.2569` captured high. It is
`0.0024322205159990062 tok/s` below the dated a047 diagnostic. Every value is
retained under its exact identity; none replaces or lowers another.

The arm used TP1/GPU0, MTP0, F16 model/KV, 32K maximum context, graph mode
`FULL_AND_PIECEWISE` with capture sizes `[1,2]`, async scheduling, 0.90 memory
utilization, and a new ext4 cache. `PYTHONHASHSEED` was absent in both Docker
configuration and PID-1 environment. All 25 prompts were unique; each returned
512 token IDs with zero cached tokens and a length finish. The code-14 canary,
GPU identity, and direct-plus-ordinary verification of all 19 model files
passed. vLLM 0ecc, kernel `baaa05bb4e`, and the official nightly base digest
were identical before and after the arm.

The new cache has 1,097 files and 38 `.best_config` decisions. Its outer cache
key is `d65565f7e2`; AOT key
`68fc8c632858eb7c65d6de5b3d4f347cb96e1b18357ec6468847d6c7010adc9d`;
code/config/compiler hashes are
`fb13d4aa1ef8a386c76ab56d39925ff4de083895d9dcbd136e778046e78bb118`,
`7fd9f3bcb2`, and `ddcad03736`. It was not replayed and is not a portable
overlay. Compared with a047, 21/25 complete token sequences match; compared
with a4d, 19/25 match. Fresh-compile/cross-boot determinism therefore remains
unresolved.

Structured evidence is in
`experiments/qwen38-27b-b70/data/2026-08-24-qwen38-0ecc-tp1-qualification-attempts.json`.
The full 1,360-entry run and cache are archived at
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/tp1-hash-unset-20260824T075527Z-0ecc284790-current-diagnostic.tar.zst`,
SHA-256
`9c760f97ddac5ff9434f201ded337bc8f6ba24babb21ce00e1dfbb90363353f9`.
The diagnostic authorizes the separately preregistered six-arm seed-zero
campaign if 0ecc remains literal current. It is not strict, natural-EOS, or
full quality-battery qualification and does not promote the current profile by
itself.
