# Reuse one complete compiler registry validation

Inactive source candidate, 2026-09-14. The preceding native-activation screen
passed nine original-output comparisons, but the subsequent exact paired screen
did not show a speed gain. This candidate addresses a specific duplicated
Python registry traversal; it does not assume that traversal explains the
measured slowdown or claim any speed improvement.

Parent: immutable `prepared-encoder-compiler-05`, manifest
`45dc23a7c0a0a234412e31a36225716edf60bb16ad342d96fe12f65139bccbe5`.
The original adapter SHA256 is
`c3f3e4ede85b2798981dca40562bd77586ad63afe55b043c0705fceddda29a1e`.

Previously, `_CompilePreRun._validate` called `_routes`, which traversed the
complete registered block/route structure via `_registered_binding(..., 0)`.
Immediately afterward, `_validate` traversed that same structure again to obtain
the selected block's binding. The candidate obtains the selected binding during
the first complete validation and removes only the second call.

`_routes(patcher)` retains its two-result API and original index-zero validation.
The optional keyword `binding_index` accepts exact Python integers0..47 and
returns `(diffusion, routes, binding)`. Negative, out-of-range, Boolean and other
noninteger selections fail explicitly. No binding is cached across validations,
denoising steps, forwards, or requests.

The complete `_registered_binding` body remains unchanged, including both shard
registrations, transformer tuple membership, all48 route placements, and selected
owner/container binding. All `_routes` patch/hook/callback/wrapper guards remain.
The lifecycle's owner, callback identity, binding comparison and device checks
remain; its pre-run and each-execution validation calls stay at their original
locations. Compiled route checks, compiler options/backend, application/removal,
registration, native math, and graph execution are unchanged.

Artifacts:

- `ltx_block_compile.original.py`: exact pinned parent adapter.
- `ltx_block_compile.candidate.py`: SHA256 `4fe9f3e8ed962a0e50e53b00734c9095290f58e6a16dcff998db5282a819b970`.
- `registry-reuse.patch`: SHA256 `5f2b45a8eb34e74fe1bce16c5f59f9b18ae077e7e78d0ecfaad794245b8b3862`.
- `manifest.json`: parent/source pins and source-check results.

The exact whole-source reverse transformation and AST checks passed. They verify
that no changes outside the three declared replacements occurred, including
unchanged registry validation and surrounding lifecycle call sites. No Torch
import, runtime test, server action, live/frozen source edit, or commit occurred.
Root owns lifecycle negative tests, native exact-output qualification, any later
packet integration, and matched timing. Those outcomes must be recorded
separately; this source snapshot itself remains unqualified.
