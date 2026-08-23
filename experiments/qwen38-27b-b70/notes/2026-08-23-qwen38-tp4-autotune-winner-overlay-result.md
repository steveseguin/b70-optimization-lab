# TP4 historical autotune-winner overlay result

Date: 2026-08-23. This closes the three-arm program frozen in the
[preregistration](2026-08-23-qwen38-tp4-autotune-winner-overlay-prereg.md).
It keeps the then-current rolling upstream runtime underneath the optimization
and preserves the pinned frontier and every stock rolling-runtime capture as
separate identities.

## Outcome

The historical Triton-winner overlay passed the preregistered definition of
stable full TP4 recovery on the newest `a3561ef8` runtime. The fresh diagnostic
arm reached **71.722545 tok/s**. Exact-cache strict replays measured
**71.352872 / 71.454271 tok/s**: both exceed the frozen `71.293263` floor, and
replay B exceeds the required `71.398430` high bar. The strict pair is therefore
an accepted, versioned `a3561ef8`-runtime overlay profile.

| Arm | Overlay tok/s | Frozen comparison | Result |
|---|---:|---:|---|
| seeded fresh, ignore EOS | **71.722545** | old diagnostic floor `71.548800` | pass; +0.243% |
| exact-cache strict A + quality | **71.352872** | strict floor `71.293263` | pass; +0.084% |
| exact-cache strict B | **71.454271** | strict high bar `71.398430` | pass; +0.078% |

The strict pair spans only `0.101399 tok/s` and has a midpoint of
`71.403571 tok/s`. This is a stable performance profile, not permission to
erase other results. The stock rolling runtime's `71.900199` single capture is
still the fastest measured value for that stock identity, while its exact-cache
repeat of `71.245742` remains the evidence that the stock high did not
replicate. The pinned `71.293263 / 71.398430` pair also remains intact under
its original runtime identity.

Report the promoted strict profile as the observed
`71.352872-71.454271 tok/s` range. The lower value is the lower observed
endpoint across the two replays, not a guaranteed or independently replicated
floor. Replay B was not itself replicated at exactly `71.454271` either.

## Then-current rolling code stayed underneath the optimization

Every arm resolved `vllm/vllm-openai-xpu:nightly` to repository digest
`sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`,
linux/amd64 manifest
`sha256:ad7d8e8ef69e3dcc1ad08339b12c0c118bf98b9602b89f66aa5efc236e1df41a`,
and vLLM source `a3561ef8e49d3545c4078df43444beb4c98ae124` before
launch. The fresh arm copied only 152 hash-matched `.best_config` decisions,
then compiled and saved a new four-rank AOT model under the current runtime
namespace.

No historical generated Python, AOT model, Triton binary, cache object,
`.kernel_perf`, or outer cache artifact was copied. The runner rejected direct
loading of an old AOT model during the fresh arm. This is the intended update
model: the then-current upstream code and binaries remained the base, while
compatible optimization decisions were carried forward under exact identity
and performance gates. Although all 152 decisions were identity-matched and
seeded, only 78/152 selected configurations differed from the fresh
`a3561ef8` choices.

The 152-file seed manifest SHA-256 stayed
`a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2`
before compile, after compile, and after the complete workload. No additional
`.best_config` appeared.

## Correctness, quality, and cache immutability

All three arms passed 25/25 unique cold benchmark rows, exact code-14 canaries,
returned-token-ID gates, and cached-token-zero checks. Strict replay A passed
the complete TP4 battery:

- 7/7 objective cases;
- 8/8 same-server repeats with one output hash;
- the requested 8K needle, with 7,617 constructed and 7,629 API prompt tokens;
- 24/24 nonempty baseline comparisons;
- cached tokens zero on all 16 quality requests.

The current-runtime cache contained 2,117 regular files. Its manifest-file
SHA-256 was
`88a62b6eab9b23700568dcc88524e599d3325bc004780ec852ed9eebf6c43f92`
after the fresh arm, before and after each replay, at each runner-final check,
and after each container was fully removed. Fresh, replay A, and replay B are
therefore exact-cache comparisons.

Strict A/B complete outputs matched on 20/25 prompts and first-100 token IDs
matched on 24/25. The speed result is repeat-qualified, but exact cross-boot
token nondeterminism is not fixed; that disclosure remains mandatory.
Multi-GPU XPU Graph is also still labeled experimental/single-GPU-supported by
the runtime.

## Recovery archive

After the capped program closed, the live ext4 compile cache was archived to
the USB evidence store as `tp4-autotune-winner-cache.tar`. GNU tar comparison
passed before removal, source and archive both had 2,678 entries, and the
635,105,280-byte archive verifies as SHA-256
`0a768ca0050521663f465dcf2d7d0fca321f44a57be0507eac742758a0a33ae1`.
Only the exact live cache directory was removed. The archive, raw roots, image,
tracked winner bundle, and runner make the profile recoverable.

## Frozen disposition

- Accept `a3561ef8` plus the TP4 historical-winner overlay as a versioned,
  quality-qualified stable performance profile.
- Preserve the pinned profile, stock rolling profile, stock `71.900199`
  captured high, and all raw values. Do not merge their identities.
- Do not claim deterministic output; keep both the cross-boot and multi-GPU
  graph disclosures.
- Do not add a fourth arm. The preregistered program is closed.
- A newer nightly invalidates this target mapping. Resolve the new digest,
  remap compatible winner decisions, compile binaries fresh, and rerun the
  sentinel gates rather than falling back to this older base.
- No LocalMaxxing submission was made; the existing human decision requirement
  remains.

Structured details and evidence hashes are in
[`2026-08-23-qwen38-tp4-autotune-winner-overlay-result.json`](../data/2026-08-23-qwen38-tp4-autotune-winner-overlay-result.json).
