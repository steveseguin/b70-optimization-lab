# Additive compiler ownership and stale-state gate

Status: **CPU follow-up passed; inactive and unqualified on XPU.**

The subsequent [executing-patcher lifecycle gate](ltx-block-compile-pre-run-lifecycle.md)
addresses the remaining owner/late-registry limits below and passes 25 CPU
checks. Its compiler metadata capture and GPU behavior remain unqualified.

The original compiler adapter, route test and receipt01 remain unchanged.
[The additive patch](../patches/ltx-block-compile-ownership-guard.patch) applies
to `scripts/ltx_block_compile.py`. The [new test driver](../scripts/test-ltx-block-compile-route-guard.py)
applies that patch only in a temporary directory and imports the resulting
adapter in memory. It reuses the original test without rewriting it. Both the
effective adapter/test hashes and the preserved original hashes are recorded.

The patch rejects foreign weight-wrapper patches, injections, model callbacks,
model wrappers and inline transformer callbacks/wrappers/patches at admission.
It checks the complete 48-block route registry against registered primary and
secondary shard lists and their expected device, primary-device and last-block
settings. A selected callback retains only model/module ownership references,
its selected index/registered slot and the original route signature. It does
not retain the patcher.

Before routing, the callback checks that its block, owning container, registered
slot and route settings still match, and rejects added hooks or non-BF16 state.
Immediately after routing, before entering the compiled callable, it repeats
those checks and verifies block state and numerical inputs are on the expected
device. Transformer-option metadata is excluded from the input-device walk:
the per-forward routing cache intentionally retains source-device references.
The numerical options themselves are passed through unchanged.

The [second receipt](../data/ltx-block-compile-route-cpu-02.json) and
[log](../data/ltx-block-compile-route-cpu-02.log) record **51 passing checks**.
Additional rejection cases cover altered registration, replaced containers,
changed transformer tuple, mutated route settings, added local/global hooks,
non-BF16 state, wrong state/input device and nonstrict deterministic mode.
All rejection cases restore the fixture's registered ownership. The arithmetic
stage places an actual compiler callback in its rich callback registry, closing
receipt01's recorded metadata-coverage gap.

The same four CPU cases, 64/256 video tokens by seeds 17/123 with 26 audio tokens,
again produced exact eager and repeated video/audio outputs. There were
**two compiled graphs, 986 captured calls, no graph breaks and two successful
AOT/Inductor compilations**. Main-process peak RSS was 1,157,128 KiB, approximately
1.10 GiB; compiler-subprocess peak memory is not summed into that figure. One
compiler worker and one CPU compute thread were used, with temporary compiler
caches removed afterward. No failed run, option sweep or additional geometry
experiment was performed.

The structural guard stage uses a bound 48-block tiny model. The numerical
stage uses the direct single-block fixture and its compiler callback registry.
These are CPU component/capture gates, not native-weight large-matrix or XPU
qualification. Device transfers between actual GPUs remain untested here.

Restoration is **dispatch-only**: restoring the original callback preserves
eager dispatch and sibling/parent registrations, but a clone's `parent` can
retain the compiled candidate and its compiler resources. This patch performs
no global Dynamo reset and makes no claim of releasing compiler or GPU caches.
Any future repeated apply/remove campaign needs an independently measured
resource lifetime policy.

Independent review identified two remaining lifecycle limits. The per-call
binding retains its diffusion/secondary owner but does not anchor those owners
to the executing patcher's top-level model and additional-model registry.
Replacing an entire owner after admission could leave the retained old owner
internally consistent while outside the executing model's accounting. Also,
foreign patcher callbacks, wrappers and injections are checked at admission;
post-admission changes to those registries are not revalidated by the callback.
Native deployment therefore requires a frozen lifecycle or a future
executing-patcher pre-run validation gate. These limitations remain recorded;
the measured patch and receipt02 were not changed to imply they were fixed.

The header's FP32 scale-shift tables need separate interpretation from loaded
state. The [source dtype audit](ltx-block-storage-runtime-dtype.md) explains why
the frozen static BF16 loader copies those tables into BF16 parameters, while
requiring an actual loaded-state census before native compiler qualification.

The protected encoder-v2 source packet and running server were not modified.
