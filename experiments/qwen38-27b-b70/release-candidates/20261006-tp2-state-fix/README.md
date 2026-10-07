# Two-card Qwen3.8 27B state-boundary release candidate

Status: **draft, CPU verified only; GPU qualification and publication pending**.
No published package, historical overlay, image, launcher or benchmark claim is
changed by this packet. No model process was launched to prepare it.

The existing TP2 recipe can read the wrong recurrent-state slot when a highly
accepted speculative step is followed by a narrower step, including at the end
of the context window. Research R314 plus the state-width overlay fixes this
indexing path. This candidate copies that overlay and rejects incompatible
registration or narrow-step layouts instead of logging an error and continuing
with the known defective path.

## Exact scope and provenance

- Target: `Qwen/Qwen3.8-27B-FP8`, revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, two B70s, one user,
  full 16-bit KV, MTP depth 5, prefix caching disabled. Qualification must retain
  the published TP2 profile's other settings and record their complete identity.
- Published control: R310 registry image
  `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04`.
- Required candidate kernel: R310 plus
  [R313 state-rounding patch](../../patches/vllm-xpu-kernels-gdn-spec-decode-exact-r313-20261004.patch)
  and [R314 state-stride patch](../../patches/vllm-xpu-kernels-gdn-spec-state-row-stride-r314-20261004.patch).
  These change `csrc/xpu/gdn_attn/gated_delta_rule.hpp` and
  `csrc/xpu/gdn_attn/gdn_attn_interface.cpp` over vllm-xpu-kernels commit
  `6d92b1bfbf32767ecda8e819613eb151e70030ad` plus the existing R310 patch.
- Research-only R314 image ID from the two-card host's
  [receipt](../../data/2026-10-04-r314/image-id.txt):
  `sha256:8b78916004ca6581822b6e1f06791f94586a6c1d265c3f63b81b49c09bee1525`.
  This is **not** a public registry digest or proof that this four-card host has
  the image. This candidate has no new image yet.
- [Original research overlay](../../overlays/b70-gdn-state-width/b70_gdn_state_width.py)
  and [original CPU tests](../../tests/test_b70_gdn_state_width.py) remain unchanged.
  `provenance.json` records their hashes and the candidate's source dependencies.
- [Research measurements](../../notes/2026-10-04-speculation-not-exact-by-construction.md)
  belong to the original overlay. They do not qualify these new guards.

The `overlay/` directory contains the copied module and its vLLM plugin
metadata. Eventual candidate launcher integration must use this directory
instead of the old state-width plugin, set `B70_GDN_STATE_WIDTH=1`, and verify
the candidate marker and required kernel identity before accepting requests.
Do not combine both versions on the import path. The module does not identify
the kernel binary or prove that a runtime's plugin loader propagates failures;
those are acceptance checks. Enabling it on the old kernel is unsupported.

## Changes and CPU verification

The candidate raises on missing or duplicate grouped-source anchors, an
unsupported builder signature, another state-width overlay already installed,
missing full state rows, inconsistent selected rows, unexpected padding, or an
unsupported graph-buffer view. Non-speculative steps remain unchanged. Full
width steps retain their tensor without extra table indexing or allocation.
Narrow steps keep the same shape and preserve the wider row backing storage.
The checks inspect metadata without synchronizing accepted counts from a GPU.

Run from this directory using an existing Python with PyTorch installed:

```bash
python test_state_width.py -v
```

The recorded run used `/home/steve/.venvs/vllm-xpu/bin/python`, torch
`2.11.0+xpu`, on `steve-b70s`, with CPU tensors only. All 20 tests passed.
`cpu-validation.txt` retains the output. No torch installation, Docker command
or device probe is required by this suite.

Tests reproduce corruption without the overlay and correct slot selection with
it for context-end narrowing and long acceptance; they cover grouped nonzero
storage offsets, graph-buffer padding, unchanged full-width behavior, an old
interface rejecting multirow strided views, and explicit failure on unsupported
contracts. A separate regression proves that a single-row narrow view remains
contiguous, retains its full backing slots, and can pass the old interface check.
Therefore contiguity rejection cannot verify the kernel version: the eventual
launcher must independently enforce the R314 kernel/library identity.
Their float64 recurrence is a stand-in. They do not establish GPU arithmetic,
engine integration, numerical parity, speed, or package safety.

## Build dependency and resource gate

No build was attempted. Exact metadata checks on this four-card host found none
of the documented two-card paths for the FP8 model, R310 build or R314 build.
Do not download duplicate weights or reconstruct a large build merely because
those paths are absent; first coordinate the owning host and inventory exact
paths/image metadata.

The existing [incremental R314 builder](../../docker/rebase-v0290/build-kernels-0.1.14.1-r314-state-stride.sh)
requires an intact R310 source and compile tree, oneDNN and sycl-tla trees,
oneAPI 2026.1.1, and its digest-pinned builder image. Those are unresolved local
dependencies here. Its historical defaults allow container swap; leave the
historical script unchanged and **do not execute it with those defaults**.

For a later authorized incremental build on the owning host, explicitly set
`BUILD_MEMORY` and `BUILD_MEMORY_SWAP` to the **same** assessed value (for
example, both `10g` only if that memory budget fits the actual build), use
`JOBS=2`, specify the verified `R310_ROOT`, and choose a new empty `BUILD_ROOT`.
Do not change host swap, cache, power settings, or overwrite either preserved
build. Check free space and actual anonymous-memory needs first. Capture the
build log, compiler inventory, artifact hashes, and portable RUNPATH. This is
incremental lab-build guidance, **not public source closure**. A public release
also needs a clean-source build that does not depend on the owning host's
compile directory.

## Next qualified acceptance

1. Coordinate with the two-card host's context-research owner. Preserve its
   process, research overlays, builds and model. Bind the candidate to an exact
   commit, kernel/library hashes, image identity, hardware and launcher flags.
2. Verify plugin discovery and activation against actual installed vLLM source;
   prove incompatible activation prevents serving. Run the real recurrent kernel
   census and a focused actual-kernel narrow-after-high-acceptance regression,
   including the context-end case. Compare output and stored state to sequential
   decode. CPU fake tests are not a substitute.
3. Prepare a dedicated candidate launcher using the TP2 package settings plus
   the qualified kernel and this plugin. Audit
   [the existing acceptance runner](../../scripts/run-fp8-tp2-acceptance-session.py)
   before reuse: it pins R310, a two-host model path, historical oracle paths,
   health tooling and a source-file list that omits this candidate. Update a
   candidate copy with explicit paths, candidate identity, overlay dependencies,
   frozen target-only references and activation checks.
4. On the selected idle/authorized cards, run the complete fixed strict suite,
   target-oracle comparison, 64-prompt oracle, practical repeat checks, and
   context-boundary/long-context cases through that launcher. Keep every failed
   receipt. Respect fault halt and one controlled shutdown; no retry/restart
   policy. Fresh-server qualification stages must each be separately planned
   and started once, coordinated with the user's persistent-server preference.
5. Complete repeated/fresh-server qualification, memory/fault receipts and a
   measured performance check. Do not transplant R314 research speed into this
   candidate's headline. Preserve the old package while these gates are pending.
6. Close the public build inputs and release assets under the
   [publication standard](../../../../docs/recipe-publication-standard.md),
   verify uploaded assets by download and hash, and run local/remote publication
   validators. Then update package/guide/dependency pins, regenerate the catalog
   and pages, run their checks, and verify deployed output. Public publication,
   performance promotion and clean-host qualification are separate gates.

TP1 is separate work. Its R312d-c image supplies `gdn_attention_ckpt` and
multiquery attention; R314 is based on R310 and cannot replace it blindly.
The existing census's TP1-shaped cases use the stock kernel, not the
single-checkpoint operator. Port state rounding to the checkpoint path and
qualify that path independently before changing its package.
