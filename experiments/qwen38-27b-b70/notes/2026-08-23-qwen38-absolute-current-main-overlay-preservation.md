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
The dated `702` run evidence, wheel/source archive, receipts, logs, and every
accepted decision/source overlay remain. No historical speed or quality value
was replaced. The new images are still unqualified; full TP1 diagnostic plus
strict A/B must pass before separate TP2 and TP4 overlay remapping begins.
