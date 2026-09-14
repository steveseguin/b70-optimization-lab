# CPU availability policy v3 — inactive; native admission unresolved

Prepared 2026-09-14. No Torch, Inductor, Kitchen or Triton import, native
compilation, model call, endpoint call or device action was performed for this
successor. The old guarded-v2 refusal and all previous sources remain intact.

The previous real attempt (PID 91112) stopped at Kitchen's registration-time
`torch.xpu.is_available()` → trapped `device_count()`. It never reached CPU
compilation or the original cache-metadata hypothesis. See
[guarded-v2-native-attempt-01.md](guarded-v2-native-attempt-01.md).

The new [harness](test_block_cpu_guarded_v3.py) installs the unchanged v2 guard,
then [cpu_import_policy_v3.py](cpu_import_policy_v3.py) replaces precisely
`torch.cuda.is_available` and `torch.xpu.is_available` with pure, zero-argument
functions returning literal `False`. This is an explicit process-local CPU
fixture policy, not hardware detection. It lasts through eager, Python boundary,
C++ boundary and both repeat arms; no per-arm enable/disable or policy retry.
No availability-call counters are introduced inside the traced functions.

All 31 existing device initialization, enumeration, property and stream traps
remain installed. Their function identities and the two policy functions are
checked after imports, before and after every model call, and before graph
census. Sticky BaseException refusal remains unchanged. Startup identity records
the requested policy before Torch import; final evidence records installation
and each completed model call identifies the policy schema. The guard's original
scope string is preserved separately, with an explicit composite description.
Compiler options, fixture arithmetic, numerical gates, operation counts,
parameter identity checks and output retention are unchanged. No cache hook,
Dynamo limit, installed source or GPU settings were changed.

## Source findings and native-admission blocker

Pinned paths, full-file SHA256s and bounded numbered excerpts are in
[guarded-v3-source-identity-01.json](guarded-v3-source-identity-01.json).

- Kitchen `backends/triton/__init__.py:343–362` tests both availability functions
  and marks Triton unavailable when both are false. An AST-extracted fake test
  verifies precisely that branch without importing Kitchen or querying devices.
- Intel Triton `backends/intel/driver.py:777–783` also delegates to
  `torch.xpu.is_available`, so the policy would prevent that activation path.
- **NVIDIA Triton bypasses these functions.** Installed
  `backends/nvidia/driver.py:54–85` calls `ctypes.CDLL`, `cuInit(0)` and
  `cuDeviceGetCount` directly; its `Driver.is_active` at 383–384 delegates there.
  The unchanged PyTorch-entry traps do not intercept those ctypes calls.
- `triton/runtime/driver.py:8–23` considers driver activation when selecting an
  active backend. Therefore the assumption that both False functions alone
  imply zero device queries is unsupported on this installed version. Whether
  libcuda exists or a call succeeds is not needed to establish the bypass;
  neither was probed here.
- `torch/_inductor/codecache.py:2305–2312` queries `triton_backend` and catches
  ordinary `Exception`. The latter selects `driver.active` in
  `torch/utils/_triton.py:243–250`. Zero active drivers would raise an ordinary
  RuntimeError, but NVIDIA enumeration occurs before that outcome. Metadata
  code remains entirely unchanged. Existing BaseException traps still escape
  its ordinary exception handler.
- `torch/_dynamo/device_interface.py:666/670` has direct CUDA/XPU device-count
  enumeration. If reached, the retained traps should refuse it; this is a
  separate possible diagnostic barrier, not a proven next runtime event.

**Do not run the native v3 harness yet.** Next prerequisite is a separately
reviewed CPU-only treatment of the direct Triton NVIDIA driver-query bypass,
shared by both compiled arms and recorded explicitly. Possible narrow follow-up
is an opaque refusal at that driver-activation boundary or a reviewed CPU-only
cache-metadata policy. Neither has been implemented here. There is no new CPU
compiled-block correctness result, GPU result or speed claim.

## Verification and preserved artifacts

[guarded-v3-stdlib-02.json](guarded-v3-stdlib-02.json) records 22 passing tests:
unchanged v2 guard behavior, every retained trap under the new policy, sticky
refusal, availability/trap identity mutation rejection, shared-arm installation,
startup metadata, extracted Kitchen and Triton-factory branches, cache exception
behavior, the unresolved NVIDIA bypass, and exact whole-harness reversal to v2.
No native dependency appeared in the test process's module table.

The first test receipt (`guarded-v3-stdlib-01.json`) has one failed source-reversal
test: its text undo removed a policy filename before removing the whole policy
load statement. This was a test-ordering bug, not a harness failure. Its exact
test source is preserved as `test_guarded_v3_stdlib-01.failed.py`; receipt 02
passes after ordering those two undo operations correctly. The harness and policy
were unchanged between both test runs.

Executed command (output must always be new):

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/native-cpp-block-01/test_guarded_v3_stdlib.py --output experiments/ltx25-b70/native-cpp-block-01/guarded-v3-stdlib-02.json
```

The complete intentional runtime-source delta is
[guarded-diagnostic-v3.patch](guarded-diagnostic-v3.patch). Harness SHA256:
`d42c828d577dc7ecc7217224804480f4eb92cee1316356d87daae50202e2d9c2`.
Policy SHA256: `03fdcf06f6de141ef7197b2b8e5a813a0929bd2bc958825c7d68f4e353843c0a`.

## Proposed next metadata hook for independent review (not implemented)

A narrow process-local alternative to allowing Triton activation is replacing
only `torch.utils._triton.triton_backend` in this disposable CPU process with a
refusing wrapper. Allow an ordinary, recorded `CpuOnlyCacheMetadataUnavailable`
exception **only** when the immediate caller's code object is the pinned original
`FxGraphCache._save_graph.__code__`, its `compiled_graph.device_types` is exactly
`{'cpu'}`, and its existing `extern_libs_key` is `None`. Reject every other caller
or metadata shape with the existing sticky BaseException mechanism; never call
the original Triton backend function. Caller inspection uses Python metadata,
without enumerating devices, tensor transfer or driver imports.

This avoids a wholesale cache-disable flag and leaves the original `_save_graph`
function byte-for-byte unchanged. Its existing `except Exception: pass` at
2305–2312 handles the explicit CPU-only metadata exception, while subsequent
serialization, graph guards and local-cache saving still run. `CompiledFxGraph`
records `device_types` in `torch/_inductor/output_code.py:612` and initializes
`extern_libs_key=None` at 644. Because the fixture uses new isolated cache paths,
the separate cache-hit metadata check at `codecache.py:2238–2248` should not need
this policy; any attempted call from that boundary must refuse, not be silently
whitelisted. A later cache-reuse policy would require separate qualification.

The hook should be installed before either backend compiles, bind the precise
source SHA256 and original caller function identity, retain all v3 availability
functions and v2 device-entry traps, and report every allowed omission with
phase/caller/CPU graph metadata. It must not call the original decorated
`triton_backend`, clear its cache, force a Triton driver, or modify registries.
Both arms must observe the same hook and refusal behavior. Native parity would
apply only to this explicitly recorded CPU diagnostic policy; it would not prove
unchanged cache metadata or native GPU performance.

Before any native attempt: independent review; source/fake tests of the exact
caller/CPU metadata gate and exception behavior (including foreign callers and
non-CPU rejection); report/hook identity checks; retain output/compiler/FX gates;
then parent-controlled single admission on an idle host. The direct device-count
paths may still trap earlier and must remain failures. This proposal has not
been implemented or exercised against native modules.
