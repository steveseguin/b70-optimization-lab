# Follow-up validation — September 12, 2026

User authorized further validation after the initial upstream reports. The
isolated checks below are complete; no production runtime or model service
was changed. This extends the earlier source-only evidence.

## Prefill fix: current-main control versus exact upstream patch

Pinned vLLM main `d8f840071efd631f71b06d4b31cb6dba2275a356` plus the exact
PR #51565 delta from head `53995de1e5781416206cabfc3ddf539611f82cc0` applied
without fuzz, offsets, conflicts, or manual changes. Both arms used the same
current-main helpers and identical fixtures:

- Stock: 14 pass, 8 fail.
- Patched: 22 pass, independently replayed by the primary reviewer.

This executes actual full builder methods, 17 upstream cases and five added
padding, reused-buffer, and mixed-chunk cases with real CPU tensors. Explicit
dependency adapters replace configuration/import plumbing; this is not an
installed-vLLM integration run or GPU graph qualification.
See [same-base packet](phase-validation-20260912/same-base/README.md).

Decision: continue supporting the existing upstream fix. The local narrower
phase guard is not preferred and remains unpromoted.

## Width fix: actual native B70 speculative operators

Pinned kernels `efc85bc8a0eb3076c861b2e6cb1e1731a93905d5`; unchanged exact
speculative entrypoints and kernel headers, with an isolated queue/registration
adapter that omits unrelated prefill/TLA code. Candidate applies the previously
archived three-file active-width patch. Neither extension was installed.

The first attempt failed before operator execution because the oneAPI 2026.0
build required libsycl.so.9, while installed torch2.11 uses libsycl.so.8. Failed
artifacts and logs are retained. Both arms were rebuilt with oneAPI 2025.3;
CPU library-loading receipts confirm only the matching venv libsycl.so.8.

The second attempt passed all preregistered cells:

| Arm | FP16 | BF16 |
| --- | --- | --- |
| Stock full width3 | Numerical/state control passes | Numerical/state control passes |
| Stock reduced width2 with cache width3 | Expected native interface rejection | Expected native interface rejection |
| Candidate width3→2→3 | All three steps pass | All three steps pass |

The shrinking step reads prior accepted history at column2, beyond the new
active width. Tokens are shuffled. Convolution state and z match bit-for-bit;
untouched SSM slots also remain bit-for-bit unchanged, including inactive
columns during shrink. Worst candidate output relative-L2 error is about
0.000024 FP16 and 0.002170 BF16; written-SSM errors are below 0.0000121 and
0.002096 respectively. Both satisfy the preregistered numerical screen; these
are tolerance comparisons, not exact model-token quality claims.

All four B70s passed preflight and postflight copy/compute checks, no new
kernel-journal faults appeared, and all input hashes matched before/after the
successful attempt. Host and per-device locks were held; no model was loaded.
Collectives were not exercised by these single-card operators.

See [device packet](width-validation-20260912/README.md),
[structured results](width-validation-20260912/device-results.json),
[successful run receipt](width-validation-20260912/device-attempt2/result.json),
and [failed loader attempt](width-validation-20260912/device-attempt1/result.json).

Decision: the reduced-width defect now has native-device confirmation, and the
small candidate passes this uniform-width operator screen. Send this evidence
to kernels issue #593. Do not promote the candidate as a complete production
fix: native ragged scheduling, mixed batches, graph capture, other shapes, and
full-model integration remain unqualified. The harness rejects ragged inputs;
it does not add that protection to the native implementation.

## Remaining boundary

The historical phantom-token anomaly remains a separate unresolved mechanism.
Neither passing operator tests nor CPU metadata tests prove it fixed. Its exact
historical FP8 model is absent on this host, and no substitute-model run is
presented as equivalent. The report remains held with its corrected explanation.

The completed work supports upstream bug handling and the bounded candidate
mechanism. Full-model/graph qualification is required before deployment; no
production promotion or performance claim was made in this follow-up.
