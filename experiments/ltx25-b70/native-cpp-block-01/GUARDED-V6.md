# Guarded v6 — native setting verified; generic registry query refused

The later root diagnostic verified the setting and completed one eager CPU
call, then halted at generic Dynamo handler registration's device enumeration.
Both GPU backends stayed uninitialized. See
[native attempt](guarded-v6-native-attempt-01.md). Do not rerun unchanged;
the source preparation below remains historical evidence.

Prepared 2026-09-14; source/stdlib work only. No native dependency import,
compilation, model call, endpoint or device action was performed by this subagent.

Parent's v5 diagnostic (PID 107105, execution session 14864) completed one eager
CPU case and stopped during the first Python-boundary compile. The exact Comfy
import omission succeeded. The captured path was VariableBuilder `_wrap` →
native `has_triton` → `get_registered_device_interfaces` → `init_device_reg` →
trapped `torch.cuda.device_count`. A second query arose during compilation-metric
unwinding; it was not a second model-call admission. V5 recorded no compiled
result, no C++ call and no cache-metadata omission; both GPU backends remained
uninitialized. `guarded-v5-result-01.json` and its log remain unchanged.

The reviewed v6 uses the existing setting
`TORCHINDUCTOR_TRITON_DISABLE_DEVICE_DETECTION=1`, set inside the disposable CPU
process **before any Torch import**. Native `torch/_inductor/config.py:592–596`
reads this setting, and `torch/utils/_triton.py:208–217` returns False before
registry access when the resulting config flag is True. Source pins/excerpts
and draft/final file hashes are in
[guarded-v6-source-identity-01.json](guarded-v6-source-identity-01.json).

[The policy helper](cpu_triton_policy_v6.py) records the prior/effective environment
value and pre-import state. The harness records it in startup identity and
compiler environment, then verifies the actual native config is exactly True
and the original native `has_triton()` returns exactly False with all hardware
traps active. It pins native function source and keeps its callable identity
unchanged. Environment/config/function identity are checked before and after
calls, at graph census and in finalization; drift forces sticky failure.

This is **one explicit CPU diagnostic compiler-configuration difference**, shared
by eager, Python compiled, C++ compiled and repeat arms. The complete compiler
configuration is therefore not unchanged. Numeric `OPTIONS`, dtypes, fixture
arithmetic, native operator implementations, the registry and device traps
remain unchanged. No function alias rewriting or device-count simulation is
introduced. V4's narrow cache-metadata refusal and v5's single Comfy import
refusal remain intact. There is no claim of unchanged GPU execution semantics.

The initial requested pure-function replacement was drafted but never run or
qualified; it is preserved in `cpu_triton_policy_v6-01.function-draft.py` and
`test_block_cpu_guarded_v6-01.function-draft.py`. Parent source review selected
the native setting because it is explicitly provided to disable device detection
and requires fewer callable mutations. Its exact replacement delta is
[guarded-v6-native-setting-vs-function-draft.patch](guarded-v6-native-setting-vs-function-draft.patch).

[guarded-v6-stdlib-01.json](guarded-v6-stdlib-01.json) records **69 passing
stdlib/fake/source tests**, with no native dependency loaded. These include the
56 inherited contracts, actual AST-extracted config expression and native
`has_triton` early-return branch with fake imports (no registry import), native
function identity, prior environment recording, pre-Torch ordering, strict
config/result checks, late-mutation/finalizer negatives and unchanged numeric
helpers. `--check-only` returns before environment mutation or native imports.

Executed command:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/native-cpp-block-01/test_guarded_v6_stdlib.py --output experiments/ltx25-b70/native-cpp-block-01/guarded-v6-stdlib-01.json
```

The complete v5→v6 runtime delta is
[guarded-diagnostic-v6.patch](guarded-diagnostic-v6.patch).
Harness SHA256:
`18fc3b783c0b78749b14d0fe5d81f5c54534550385b166b3c4234a17f1255aa6`.
Policy SHA256:
`6feb786c72e07a611abb3c339087b09465074f832ab169d739c20ec883302dfd`.

Parent owns source review and any separately scheduled single native diagnostic.
Another trapped query remains a possible outcome. These tests establish no CPU
compiled-block numerical result or GPU/speed improvement; all existing exact
output/compiler gates still need to pass natively.
