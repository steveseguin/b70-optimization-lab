# Guarded v7 — virtual CPU fixture registry, inactive

Prepared 2026-09-14. Implements the reviewed
[CPU registry proposal](CPU-DEVICE-REGISTRY-PROPOSAL-01.md) as new source only.
V6 and its failure evidence remain unchanged. No Torch/Kitchen/Inductor import,
CPU compilation/model execution, endpoint or device action was performed while
preparing v7. Parent owns any later native admission.

[The registry helper](cpu_device_registry_policy_v7.py) imports only stdlib. It
requires the exact pinned device-interface module, original registration and
accessor code/globals, an exact empty original dict, and initialized flag False.
Partial, preinitialized, foreign or previously qualified state is rejected,
without clearing or repair. If generic handler construction is already loaded,
its code must match the pinned native method and its cache must still be empty.

The helper calls the original `register_interface_for_device` for precisely
`cuda`, `xpu`, `mtia`, `cpu`, `mps`, `tpu` in that order, using the corresponding
unchanged native classes. After exact mapping validation it marks the native
initialized flag True. It never invokes `init_device_reg`, device_count, streams
or property queries. The resulting mapping equals native initialization with
three zero-iteration device-enumeration loops; this is an explicit virtual CPU
fixture policy, not a statement about available hardware or equivalent GPU
compiler semantics. There are no indexed entries and no class/function/dict
replacement.

Captured CUDA/XPU device/query/property/stream aliases must match the previously
installed guard and Comfy import wrapper. Native raw-stream aliases must be None
where originally unavailable or the installed C-entry trap. The original generic
stream/current_stream/Event handler object identities are preserved. The helper
records ordered entries, class/handler/dict identities, pre/post initialized
state and handler-cache admission metadata.

The [v7 harness](test_block_cpu_guarded_v7.py) installs the registry once after
all prior guard, import and Triton policies and before Kitchen/fixture imports
and compilation. Both compiled arms/repeats share it. Per-call checks, graph
census and finalization reject dictionary/class/order/ordinal/function/alias/
initialized-state mutation; no rebuild occurs. Startup and completed-call
receipts identify the policy. Numeric OPTIONS and arithmetic, frozen hardware
traps, v3 availability False, v4 cache metadata refusal, v5 Comfy import refusal,
v6 native device-detection setting and exact numerical/graph gates remain.
The complete CPU compiler state intentionally differs from the original runtime.

## Verification and preserved iterations

[guarded-v7-stdlib-03.json](guarded-v7-stdlib-03.json) records **28 passing focused
stdlib/fake/source tests**, including v6 policy contracts. Earlier v6/v5 suites
remain separate evidence, not silently counted again in this receipt.

The tests extract the actual native registration/init/accessor functions into a
fake-module fixture. A reference native initializer calls three fake counters
returning zero; v7 construction calls no fake original hardware functions. Both
produce exactly the same ordered native-class mapping and duplicate-removed
stream/current_stream/Event object sets. Tests also exercise captured traps,
pristine-state and cache-admission refusal, absent ordinal lookup, all relevant
late mutations, finalizer failure, and preserved parent/numerical helper code.
No actual device/registry module is imported or executed.

Receipt 01 failed because the fake fixture used the same local name `stream`
in its class assignment, causing a Python class-scope NameError. The failed test
source is preserved. Receipt 02 passed 27 tests after a test-only name correction.
Receipt 03 adds the explicit original-handler-code empty/populated-cache case;
its pre-addition test snapshot is also preserved. The registry policy and
harness did not change between these receipts. Exact test deltas:
[guarded-v7-test-fix.patch](guarded-v7-test-fix.patch).

Executed final command:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/native-cpp-block-01/test_guarded_v7_stdlib.py --output experiments/ltx25-b70/native-cpp-block-01/guarded-v7-stdlib-03.json
```

Runtime delta: [guarded-diagnostic-v7.patch](guarded-diagnostic-v7.patch).
Source/receipt pins:
[guarded-v7-source-identity-01.json](guarded-v7-source-identity-01.json).
Registry helper SHA256:
`f6fe6e2723f9fb71cfe8bc627f7f2df0531d4720ea0ca8b96a854c61b71490a1`.
Harness SHA256:
`ac75b4bffe6449a939fed91ae07b494aec867a858e0615a87e64566549c57da2`.

Parent review and a separately scheduled native attempt are still required.
No CPU compiled-block numerical result, GPU result or speed improvement has
been established. Further unexpected native queries must remain diagnostic
failures with preserved first evidence, without automatic expansion or retries.
