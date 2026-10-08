# Inactive111 native conditioning stage guard

This CPU-only module wraps two trusted native calls. It does not register nodes, build a packet, admit a request, inspect a live model, submit inference, write receipts or qualify continuation. Root owns the separate encode-OOM source delta. The22 synthetic tests import the exact sealed110 NativeReferenceSafety module, with synthetic resident objects and memory/cache callbacks; no Torch import or device call occurs.

## API and ordering

Construct `ConditioningStageGuard` with the exact110 controller and four trusted callbacks: `tensor_metadata(tensor)`, `inspect_anchor(image)`, `inspect_encoder_cache(encoder, thread_ident)`, `unwrap_output(native_result)`. The docstrings give exact callback schemas. The controller class source file must hash to the pinned110 source; this is not proof that loaded Python methods or supplied callbacks are unmodified. Future runtime source closure must provide that proof.

Inside the existing `NativeAdapter.before_request`/`after_request` scope:

1. For conditioned chunks only, call `begin_request(request_id, anchor=image, expected_anchor_sha256=...)`. The controller must already have that exact active request. Chunk0 makes no conditioning guard calls.
2. Call `run_stage('A', request_id=..., vae=..., latent=..., native_call=...)` before samplerA, then exactly one `run_stage('B', ...)` after latent upsampling and before samplerB. Lowercase aliases are refused. The guard invokes the callable with its bound image, supplied bound video VAE and latent, `strength=1.0, bypass=False`.
3. Call `finish_request(request_id)` while the controller still owns that active request, before `adapter.after_request`. Finish requires both completed stages; at most four conditioned requests are accepted for the three-chunk chain plus replay. The native returned object is preserved unchanged; the trusted unwrap callback extracts its one LATENT result only for metadata inspection.

Do not close/replace the controller or disable the whole-request no-eviction context around these calls. Finish does not establish full-request completion: the existing executor post-memory, four-tensor finite/exact gates and durable authority completion must follow. Native exceptions, including OOM, propagate unchanged after both guard/controller failure latches are set. No failed stage/request is retried. Reentrant calls fail even if native code tries to swallow the inner refusal.

## Integration obligations, not claims made by callbacks

Bind native_call to exact source `LTXVImgToVideoInplace.execute`; bind graph run_name/stage/image/VAE to the admitted request and immutable predecessor provenance. The graph's image must be the same object as the guard's bound anchor. Pin actual node registration, method identity, all source dependencies and the separately transformed encode source. Ensure encode OOM calls the attached safety owner before tiled fallback/cache clearing, alongside the retained decode hook. This wrapper alone cannot intercept a swallowed OOM inside an unmodified native encoder.

`tensor_metadata` must obtain actual object/storage ownership and shape/dtype/device/contiguity without tensor arithmetic. Storage identity must describe underlying storage, not just a shifted view pointer. Inputs/outputs here are CPU/F32; clone output, mask, latent input and anchor must have distinct storage. The guard checks metadata and freshly invokes `inspect_anchor` before/after stages; that callback must actually verify finite full-float bytes and predecessor SHA, not echo the expected string or reuse a cached answer. Enforce exclusive immutable anchor ownership and retain it through both native calls and full request completion. Full tensor finite/value/mask semantics and native exactness remain the four-tensor reference/replay gate's job; metadata equality does not prove samples unchanged.

`inspect_encoder_cache` must inspect the actual bound VAE's actual encoder and current thread, verify the pinned encoder implementation, and enumerate its temporal-cache entries. It must report zero calling-thread and foreign-thread entries; returning a asserted zero without inspecting is not evidence. No other VAE/pipeline owner is admitted. The guard performs no cache removal and never replaces native encoder cleanup. Failure-time cache inspection is CPU-only and best effort; it never masks the original exception or performs device synchronization.

Both stages use fresh controller snapshots with8/8/2/9GiB before and2GiB/card after, preserving its phase/source/full-residency/fault checks. Receipts expose source-derived expected encode input[1,3,1,192,320]/[1,3,1,384,640] and estimates68,812,800/275,251,200 bytes. These are not observations inside VAE.encode or measured peaks. The exact native node derives resolution from latent×32, resizes only when needed and invokes unchanged encode loader checks. The111 integration must verify the loaded VAE scaling/dtype/intermediate settings and the transformed source; no new lower-level shape observer is implemented here.

Record and durably bind both `guard.receipts` and `controller.receipts`, including failure paths. Stage receipts include controller start/end ranges so a refused pre/post snapshot remains available even when no successful snapshot return occurred. Normal stage evidence includes source/runtime/request/anchor bindings and metadata; bounded failures retain exception class/reason, incomplete stage and best-effort cache evidence. The guard keeps at most four request identities; expected request names are limited to128 safe characters. Receipt persistence and byte budgets are the integration owner's responsibility, as are controller-wide receipt growth and bounded metadata scans.

Before allowing chunk2/replay, integration must bind the first conditioned chunk's two successful stage pairs, full capture/header/finite proof and post-request memory receipt in a durable barrier. This module does not implement that authority or provider. Missing finish, bypassed wrapper or skipped callback cannot be detected by a guard that was never called; future dispatcher/plan tests must enforce actual graph-to-guard execution coverage.

## Why CPU/F32 is required here

EmptyLTXVLatentVideo creates zeros on the intermediate device; bind actual default dtype to FP32. CFGGuider.inner_sample explicitly converts samples to torch.float32 before process_latent_out; BaseModel.process_latent_out delegates to the LTXAV→LTXV→LatentFormat inherited process_out (divide by scale_factor1.0), preserving that dtype. SamplerCustomAdvanced moves the returned samples to intermediate_device. AV separation unbinds without conversion. LTXVLatentUpsampler restores input_dtype and intermediate_device. The sealed launcher lacks GPU-only/FP16-intermediate flags. Future runtime must recheck these policies; capture serializer F32 alone is not evidence of intermediate dtype. Unexpected input dtype/device is refused, never silently converted by this guard.

## Validation and source pins

Command: `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s experiments/ltx25-b70/recovery/20261007-continuation111-safety -p 'test_conditioning_guard.py' -q`

22 tests passed in0.015s. Coverage includes exact original NodeOutput and call arguments, stage order/duplicates, unsupported stage aliases, four-request cap, missing finish, active request/thread changes (including inside native call/snapshot), source/controller/VAE ownership, anchor hash/finite/storage/shape changes, input/output dtype/geometry/alias, all-card low pre-memory, partial failed post-floor evidence, cache source/owner/thread/residue, OOM identity/no retry, reentry and faults. Tests are synthetic CPU checks, not encode peak, kernel/numerical or runtime integration evidence.

- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/scripts/native_safety.py`: `8a98f462417c4e5b630bbeb023666acc3829f8248361fb3b8ce0f73fa998fa0c`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/comfy/sd.py`: `d1c63b66a6d0cf467ecb084d7ec5fb73d20b0fac43181668124a8ded06aa7604`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/comfy/samplers.py`: `f2c264ca9d394612f828e3ffe167c856a278a10e1711b269f0ba65dccb66393f`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/comfy_extras/nodes_custom_sampler.py`: `b0ba1521c72475e06fed15db004274ed7c8bb2bf73f1d58849faf6f9f9d264fe`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/comfy_extras/nodes_lt.py`: `09ddb30d42244d64ae72e9c64261d1a6b4c512afe0570372222c43dbebd64243`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/comfy_extras/nodes_lt_upsampler.py`: `c9f225e4c54f19f31452016fd4e546119d69e9dec37b60a9dc4ddf133848a892`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/comfy/ldm/lightricks/vae/causal_video_autoencoder.py`: `42010d800e6e49bdc69ae24587910b55b2418e26a1140bec7159a873276c45c2`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/comfy/latent_formats.py`: `8f012cea828736e9fe1ac1753f67dfdbeade79cfeba48d5bc26d4c58549ed759`
- `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/comfy/model_base.py`: `a1a1a7bb89a199710f996bf0bdf549d3e42484fe4dd91aa0a6361bb30c990508`
