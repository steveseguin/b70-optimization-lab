# Small-state clone policy guard

The original candidate and its 12-test receipt remain preserved. Independent
review identified a missing entry guard: a fully resident ModelPatcher clone
could toggle its private small-state option and enter `partially_load`, which
returned early before consulting the original `_ltx_small_state` guard. This
bypassed the documented policy even though it did not immediately change data.
The inverse toggle, from a loaded control model to enabled, also returned early
without installing the small-state policy.

The additive [policy guard patch](../patches/encoder-small-state-policy-guard.patch)
applies **after** the original residency patch. It records the applied policy
on the shared model and checks it at `load`, `partially_load` and
`partially_unload` entry. A differing clone policy is rejected before changes
when any accounted weights, marked modules or scalar buffers remain loaded.
Complete detach clears the model-owned policy. Complete partial unload to zero
also permits a later policy change because no owned loaded state remains;
ordinary graph variants use explicit complete detach/replacement instead.
A never-enabled control keeps its original metadata and same-policy fully
resident requests retain the original fast return.

The [follow-up CPU harness](../scripts/test-encoder-small-state-policy.py)
reproduces the original bypass and then checks both toggle directions,
unchanged-policy clones, complete detach followed by a deliberate policy change,
and all 12 previous tiny real Gemma4 lifecycle tests. **17/17 passed**. The
[receipt](../data/encoder-small-state-policy-cpu.json) binds both patch hashes;
[full output](../data/encoder-small-state-policy-cpu.log) names the tests.
These are CPU bookkeeping and arithmetic checks, with no XPU residency,
latency or full-model equivalence result. No loaded source or server changed.

The subsequent real CLIP-constructor integration check found that stock CLIP
installs `object_patches={"manual_cast_dtype": torch.float32}` before its first
possible load. Rejecting every object patch therefore prevented ordinary CLIP
use. The final additive patch permits exactly that setting on an `is_clip`
patcher, without changing it; all other object patches remain rejected. Its
additional CPU test checks the allowed baseline setting and rejects FP16. The
[pre-CLIP guard](../patches/encoder-small-state-policy-guard-pre-clip.patch) and
[16-test receipt](../data/encoder-small-state-policy-cpu-pre-clip.json) preserve
the narrower earlier candidate and explain why it was revised.
