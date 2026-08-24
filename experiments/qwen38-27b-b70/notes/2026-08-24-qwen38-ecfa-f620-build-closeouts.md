# ecfa and f620 absolute-current build closeouts

## Outcome

Two literal-current successors were built with no source overlay and with GPUs
hidden. Both completed the current-vLLM/stock-kernel image and the
current-vLLM/current-kernel image, including image inspection, imports, DSO
checks, and the expected bounded `pip check` exceptions. Neither identity ran a
hardware gate, model server, benchmark, quality request, or GPU arm.

The ecfa build reached vLLM
`ecfa7bb37316a3c1dab345fea4178d81f63b1ce4`; the retry correctly synchronized
to the newer `f620499ee3fe18131d71b02e1e8e5f1cf984cf1c`. After f620 completed,
canonical `main` advanced first to `4c56e62c85cea8fc2251efc25159836c214402aa`
and then to `29c9af5211e618bfb78c4140db9e814f1a838aa7`. Both completed builds are
therefore dated evidence only and are closed stale before qualification.

XPU-kernel `main` remained
`baaa05bb4e92901219a5a072dd63f2474896f6d1` and the official nightly index
digest remained
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.

## Storage finalization and recovery

The ecfa build and then the f620 build each exhausted the root filesystem only
after both image exports had completed. In each case the failure was a write to
the final tag/aggregate-receipt path, not a wheel, image, import, linkage, or
runtime failure. Unused and reproducible Docker builder cache was pruned; no
model, run, quality, overlay, or promoted-result artifact was removed.

The ecfa pair is recoverable from:

`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T150253Z-ecfa7bb373-baaa05bb4e/images-ecfa7bb373.docker.tar.zst`

- compressed SHA-256:
  `a5e416b2e8e7627bc64a50307f8f91305041718054339125a4826ffe0b83eaca`;
- compressed/uncompressed bytes: `5805471787 / 5819666432`;
- 51 safe tar entries, exactly two expected tags, 28 layers per tag;
- `zstd -t` and traversal validation passed;
- its complete build root was moved beside the archive, then only the two exact
  local ecfa image IDs were removed.

The f620 pair is recoverable from:

`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T150930Z-f620499ee3-baaa05bb4e/images-f620499ee3.docker.tar.zst`

- compressed SHA-256:
  `dcc63c4decfcc02655b8b06fe73edf717faa789b17b66a1fd4cfdf57d58d2318`;
- compressed/uncompressed bytes: `5805570540 / 5819674624`;
- 51 safe tar entries, exactly two expected tags, 28 layers per tag;
- `zstd -t`, traversal validation, and the 15-file packet `SHA256SUMS` passed;
- packet `SHA256SUMS` SHA-256:
  `a8972876d9aff8ca6cc3e034b2c32745b4dc50b114bf02d9646fe186ceb356bc`;
- its complete build root was moved beside the archive, then only the two exact
  local f620 image IDs were removed.

The f620 aggregate receipt was recovered explicitly from the frozen source
identity, immutable image inspections and labels, exact source/wheel/static
preflight hashes, and the unchanged official kernel artifact receipt. Its
`receipt_recovery` and `stale_observation` fields make the ENOSPC recovery and
later upstream movement explicit; it does not claim the normal builder
finalization ran.

## Performance and overlay disposition

No captured decode speed changed. In particular, the protected TP1, TP2, and
TP4 floors/highs remain append-only. The TP2 78-decision artifact and accepted
TP4 152-decision artifact remain intact and were applied to neither zero-overlay
build. No compiled output was carried.

The ecfa-to-f620 delta does not intersect those decisions or any accepted patch
path. One generic FlashAttention metadata constructor is reachable by the Qwen
target and native-MTP setup, but Qwen geometry remains TP1 `24/4/256`, TP2
`12/2/256`, and TP4 `6/1/256`; XPU uses FA2 while the changed scheduler metadata
is consumed by FA3. This does not waive full MTP0 graph qualification at
TP1/TP2/TP4, and it justifies a bounded native-MTP boot/canary sentinel after
the target anchors.

## Next action

Commit and push this stale closure, resolve all three moving inputs again, and
build whatever literal vLLM head then exists. Never launch a dated image. Once
one current identity survives the live seal, run the frozen untreated TP1
control/both-current program, then remap only hash-compatible decision files
into fresh caches and fully qualify TP2 and TP4. Generated kernels and outer
caches are never copied.
