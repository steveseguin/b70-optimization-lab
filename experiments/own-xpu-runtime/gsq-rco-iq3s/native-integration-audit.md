# Native integration audit — SC117 IQ3_S

Source audit, 2026-10-24. No model execution, device enumeration, compilation, service operation, or model payload read was performed for this note. The CPU format proof establishes decoding arithmetic; it does not make the downloaded model runnable in the existing ELF.

## Authoritative starting point

Use P195's **copied P194 v5 native implementation**, not P195's older top-level `main.cpp`. `ops/packet195-orchestration/inputs/packet194-native.json` and P195 `reuse_build.py` bind the byte-reused native ELF `b8482321769039274daf42b70f783517177cbc8c1d0b2d81b8ebab25f1442bdc`. The useful source is P195 `diet-native/native-src/{entry-main.cpp,main.cpp,mtp.hpp}` and its `diet-native/native-base/.../packet194-expert-diet-engine/` dependencies. `diet-native/engine-commands.json` records the actual P194 v5 entry compilation and link. Its absolute checked-header includes must be deliberately relocated into a private new source closure; copying the entry alone would still compile old files.

Preserve the two-rank protocol, target verification/rollback, immutable draft manifest and existing lifetime owner. Introduce an explicit new-model direct-packed mode with a separate identity and admission. Do not pretend an old selection file or `--nongemv core` changes all required paths.

## Actual formats and available arithmetic

Counts below are launches in the retained, unfused `graph/new-plan.json`, not unique allocations or measured work.

| Role | Formats and launch counts | Existing native support / required work |
| --- | --- | --- |
| Dense | BF16 484; Q8_0 96; Q6_K 89 | Original `kopt::gemv` supports all three, including explicit BF16/F16 activation/output and an SG32 adjacent reduction tree. Bypass shape-selected registries and expanded storage. |
| Dense | Q4_K 43; Q5_K 31; IQ4_XS 42 | True missing native packed decoder dispatch in the inherited implementation. The new `native-formats/` operator must supply these device bodies; CPU `formats/` alone is insufficient. |
| Routed experts | IQ2_S 40; IQ3_S 20; IQ4_NL 39 | Existing `kopt4` expert arithmetic supports these; original `kopt::routed_gemv` is a simpler direct-packed alternative with per-slot inputs and explicit status/tail behavior. |
| Routed experts | IQ3_XXS 34 | Decoder and generic `kopt::routed_gemv` already exist, but `performance::experts` does **not** select them: its quantized facade only reaches the three types above. Wire a real route-aware generic operator. |
| Routed experts | IQ4_XS 2; Q2_0 9 | Missing native decoder dispatch, together with route/status/output binding. Q2_0 is this pinned upstream type 42, block 64 / 18 bytes. |
| Host lookup | IQ4_XS embedding; IQ4_NL PLE | Extend the actual Engine host lookup decoder for IQ4_XS; PLE arithmetic exists. Do not allocate or decode the entire embedding/PLE as an accidental intermediate. |

`kopt::routed_gemv` indexes input as `slot * columns`; a gate/up path using a single shared activation must use the new explicit shared-input mode or retain actual gathered per-slot inputs. Expert down uses separate slot activations. Do not route both through the same implicit input convention. Use complete owned allocation bindings, row and route bounds, status outputs, and NaN-filled unused output tails. The proposed new facade's direct-packed storage makes no indirect-cache ownership claim.

Non-GEMV controls are **293 distinct graph-derived tensors: 292 F32 and one F16**, disjoint from GEMV and lookup roles. The F16 tensor is PLE convolution. My earlier broad BF16-control concern was incorrect. Canonical F32 upload for these exact names resolves the parallel adapter's F32/BF16 gain convention without changing tensor descriptors: copy F32; widen F16 exactly; set the effective submitted `Spec.grids` to F32. No `1+w` transform belongs in this upload. Operator normalization semantics and the draft's separate official offset-gain conversion remain unchanged. `controls/upload.hpp` and its bounded test/build recipe were reviewed before root's execution; NaN tests establish classification, not F16 NaN payload preservation.

## Concrete change map

1. **Authenticate and describe the new model.** Replace the Engine's hard `paths.size()==3` admission with the exact pinned two-shard manifest. Keep the loader's existing split ordinal/count/total coverage, duplicate, extent, alignment and stat checks. Extend the actual loader/layout and directory grid-name/type conversions for Q2_0/Q4_K/Q5_K/IQ4_XS, plus directory F16 and IQ3_XXS. The original decoder already knows the latter two, but its directory whitelist does not. Bind the 1224-tensor census and tokenizer/architecture hashes; do not reuse old tensor offsets or basename authority.
2. **Make a genuinely unfused target plan.** Bypass unconditional `p39::fuse_plan`, selected route/gather and combine/norm fusion, small-GEMV groups, `other_fused_site`, HC fusion, p49c early HC gates, p74/p183 and selected expert branches. Preserve explicit original graph dependencies and status checks. The gate/up pairing can remain an organizational operation only if it issues independent correct gate/up calls and preserves their original consumers.
3. **Make storage agree with dispatch.** In `load`, `weight_variant`, `matrix`, placement and census, use direct GGUF packed bytes for the new generic path. Bypass p49b planes, p90 halfcache, p100 down tiling, packed/expanded weight transforms and old tuple registries. A new issue branch after those transformations is too late. Record effective type, raw row stride, input mode and output type in the captured operation. Do not reuse old prepared Matrix pointers after rebuilding storage.
4. **Issue through owned native operators.** Add the missing format device arithmetic and wire the actual Engine before selected special cases. Existing core non-GEMV `iq3::step_operator` is a real SYCL single-task correctness fallback, not a host substitute; parallel primitive submission with the corrected control upload is another existing path. Keep original route, QSA, GDN, PLE, HC and MoE semantics rather than substituting toy math. Their numerical results are not yet qualified on this model.
5. **Rebuild the changed dependency closure.** Header enum/decoder changes affect loader, directory, host lookup, runtime, performance and device templates. Rebuild every changed consumer in the new closure; unchanged opaque objects may be reused only with explicit source/ABI pins. Preserve strict no-contraction/no-fast-math device flags. A compiled kernel image is preparation, not device correctness evidence.

## MTP is reusable, with one important head boundary

The local official draft is already present: 3101 manifest tensors in 28 stat-verified files on the NVMe filesystem, not RAID. Its loader still checks each tensor payload hash at actual load. No additional 4.14 GB Q8 draft download is needed. New target hidden states have the same structural/tokenizer contract, but acceptance and quality are unmeasured. The additive `mtp/` proof reuses the real host controller and tests confirmed-token indexing, rejection rollback, stale/failed providers and target-only equivalence on synthetic inputs; it does not run DraftRuntime or the new model.

**Do not silently share a packed target head with the old expanded draft head.** Actual `mtp.hpp` initialization requires `head_candidate == p33.dense.segment` and variant 6, then shares the resident target head allocation or loads an expanded Q6 head. Minimal alternatives are (a) preserve that supported expanded-Q6 head as an explicit isolated exception in both placement and submission, or (b) change draft head loading/submission to the same new packed facade and share only matching storage. Start with a full-vocabulary policy; the old 80128-row calibration is not evidence for this model. Target head splitting/placement and draft head sharing are separate choices that must agree on physical extents.

Preserve the one-token confirmed-input protocol: draft consumes confirmed token at position p with target hidden state p−1 and draft cache position p−1; target verification alone commits output. Keep existing mismatch rollback and provider-disable behavior. First validate the new target-only path, then enable the same-binary MTP branch and demand exact target-token/state equivalence. That sequence preserves MTP implementation without attributing new-model correctness or speed to the old record.

## Smallest useful completion gate

Finish the new native-format operator and the explicit generic Engine overlay, then compile the real two-rank executable with MTP code retained. Before any device window, use a header-only loader/plan pass and allocation census to prove complete format coverage, authentic two-shard offsets, no old selection escape, controls conversion, correct captured storage and draft-head compatibility. Reuse bounded Host tests for owned binding and protocol edges. The first separately admitted native qualification should cover the actual changed operators and a short new-model target-only transcript before same-binary MTP equivalence; it must not substitute an old-model token oracle.

Raw non-lookup linear weights total 54,704,563,200 bytes, excluding controls, draft, recurrent state, temporary buffers and driver reservations. PLE is another 28,800,138,240 bytes in host-backed storage. These are source-derived sizes, not a two-card fit or bandwidth claim; recompute per-rank placement and host headroom, including current applications, before launch. No new performance or acceptance estimate follows from this audit.

## Source identity

The following small source/metadata files were hashed for this audit; no ELF or model payload was rehashed. 14 copied native source/command files also matched the P195 native-binding manifest. Paths are repository-relative.

| Path | SHA256 |
| --- | --- |
| `experiments/own-xpu-runtime/ops/packet195-orchestration/inputs/packet194-native.json` | `237e1e14dfc584e0550d9e0882cd3933035a1e22aca400805123fc1056da7433` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/reuse_build.py` | `05eeb81d06ba23b2a6ab160d0b045b75582ff3eea837fcbf446aef8410fa618a` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/engine-commands.json` | `9af8e57f6352ed3cabd0d6c5f47185985a528b71f165a3f4b52b25550f32d0ce` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-src/entry-main.cpp` | `8bf9d77ea962ebe23a895b589049f94d3681daf8e14b52ecf9ad8a6eca826815` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-src/main.cpp` | `8a712b8ea9fb7cc2f0b68ba58bb2c156812bdef7cecc1f5f064abfde101f2bce` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-src/mtp.hpp` | `e9f983b1e951e5bef2381c12eff33c186af31cf557da6d1e10de9e8d690c614b` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/performance.cpp` | `01e07190573fd0a6cf8b147d89fcf9e329db95e6111bde575273c64f522858c2` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/adapter.cpp` | `0f808acc16047c4bf6a74b4322a4e635ddc690affc77e836c1bade5e8ef876e4` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/core_v2.hpp` | `97fd765f3bc2dd587f3898d81259adcc5ba32a5c98b4714ddd64e36a8d69ac3f` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/runtime_kernels.cpp` | `4677e61554e9568e17141e26b9211eec89150a97ce22a45511fbce6f176feed5` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet2/loader/gguf.cpp` | `982aca9578d6f5fa801052dac54e558a1eda35e53700281f244f68ea12f39934` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet2/kernels/math.hpp` | `e06361e86cfd122644c2818ae09d2e2511216a300e5b828051136c254540bfca` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet3/model/directory.hpp` | `5a91e6baa6c8569ab7edeaa091af3eae5e9a3720a3e5d59925801fd691c8821e` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet6-kopt/kernels.cpp` | `fb584f02f488a1a370d5aeb6329228a4e3aeef2dee19a92c84f8e6752b181f6d` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet6-kopt/reference.hpp` | `c394ba8033cbc9ef0a6a55602c9d684452f701e6c9d3fe7c757b59017df742f7` |
| `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet9-kopt4/kernels.cpp` | `f087dc80a9c75dcfdd5df095aab6276a67e35104aef5bccec64bf743f8172739` |
| `experiments/own-xpu-runtime/gsq-rco-iq3s/graph/new-plan.json` | `4d37ea499b0994a69664309d8f3c88aefc908e5034ac441b63f02e02151cf78b` |
| `experiments/own-xpu-runtime/gsq-rco-iq3s/metadata/new-census.json` | `b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1` |
| `experiments/own-xpu-runtime/gsq-rco-iq3s/controls/upload.hpp` | `06faa21c3d2b5bf2c73613fc64f32395099f07c4d16d488e59204c1b1ac69848` |
| `experiments/own-xpu-runtime/gsq-rco-iq3s/formats/independent-review.json` | `1f38afc95bd07b749cd997d67ddf6d5071ff07c62e04823f25f5800c3590c7ba` |
| `experiments/own-xpu-runtime/gsq-rco-iq3s/mtp/evidence/receipt.json` | `2c67c34dbf0e5e1733a820d0bb28a0e2c6c1bc35a53000315ddf8af953b01f4f` |
