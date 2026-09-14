# Guarded v5 — Comfy import fixed; compiler detection refused

The later root diagnostic completed one eager CPU call, then refused device
enumeration during the first Python-boundary compilation. Both GPU backends
stayed uninitialized. See [native attempt](guarded-v5-native-attempt-01.md).
Do not rerun v5 unchanged. The preparation account below is historical.

Prepared 2026-09-14. V5 preserves the earlier sources/results and adds one shared
import helper. It has not imported Torch/Kitchen/Inductor or run native work.

The parent-owned v4 diagnostic exited 1 (PID 105412, execution session 5978).
Its sole trap was the unconditional `torch.xpu.device_count()` in the actual
`comfy/model_management.py:127` during import. Comfy's bare exception handler
caught the initial BaseException; the sticky guard then halted metadata binding.
There were zero model calls and zero cache-metadata omissions. Both XPU and CUDA
reported uninitialized at exit; no fault latch was present. Parent postflight at
17:19:46 reported unchanged full endpoint identity, idle server 84255, expected
render owners and clean kernel output. This is a guarded import refusal, not
observed device failure, native compilation, or numerical qualification.

The original evidence remains in `guarded-v4-result-01.json`,
`guarded-v4-run-01.log`, `guarded-v4-startup-01.json` and
`guarded-v4-postflight-01.json`. Their hashes are preserved with the successor in
[guarded-v5-source-identity-01.json](guarded-v5-source-identity-01.json). Parent
also recorded the actual outcome in `guarded-v4-native-attempt-01.md` and updated
`GUARDED-V4.md`; those files remain unchanged by this successor.

## Narrow successor

The shared helper is
[../scripts/cpu_comfy_import_policy_v1.py](../scripts/cpu_comfy_import_policy_v1.py).
It installs after frozen `accelerator_guard_v2.install` and before v3's
availability policy captures the device-count wrapper identity. It accepts an
explicit absolute model-management source path, permitting the identical pinned
source in an immutable packet. Exact source SHA256 is
`ef3f3af0657c1b022ad69b25928fa52dd429db9aed9cb688e89c7fbe68ab50cd`.

The helper raises an ordinary RuntimeError refusal only on the first and only
no-argument query from that exact source's top-level code, with the actual
importing `comfy.model_management` module's globals, source path and torch object,
`args.cpu is True`, and phase `guarded-Kitchen-Inductor-import`. Comfy's existing
exception handler then leaves `xpu_available=False`. This does not return a
synthetic device count or call hardware. Every other call delegates to the
original frozen Python trap and preserves its sticky BaseException behavior.

`finish_import(actual_module)` binds completion to the captured module, requires
exactly one omission and `xpu_available=False`. The wrapper remains installed
through both compiled arms and repeats. Integrity checks after import, before
and after model calls, before graph census, and during finalization require the
same wrapper/module and exactly one completed omission. Finalization forces
failure if an import omission is missing, duplicated, or tampered with.
The additional finalizer works even when import fails before v4 metadata policy
installation. V4's metadata refusal, v3 availability policy, frozen guard,
fixture/OPTIONS and all numerical/compiler gates remain unchanged.

Shared API for other CPU fixtures:

```python
controller = ComfyImportPolicy(torch, report, guard,
    model_management_source=source / 'comfy/model_management.py')
# Install availability policy after controller so it captures the wrapper.
report['phase'] = EXPECTED_PHASE
# Existing actual fixture imports occur here.
controller.finish_import(sys.modules['comfy.model_management'])
controller.require_intact(require_complete=True)
```

This helper is not an import endpoint and does not execute supplied source. It
checks the fixed SHA and compiles source to a Python code object for comparison.
It cannot silently permit registry device enumeration, CUDA queries, later XPU
queries, or another model-management revision. No registry policy was added.

## Verification and handoff

[guarded-v5-stdlib-01.json](guarded-v5-stdlib-01.json) records **56 passing
stdlib/source/fake tests**. This includes the inherited 39 v4 tests plus import
ownership/code/phase/CPU checks, bare-exception swallowing with sticky refusal,
duplicate/query-after-import negatives, retained hardware traps, completion and
finalizer failures, and unchanged frozen v4 files/numerical helpers.
No native dependency appeared in the test module table.

Executed command:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/native-cpp-block-01/test_guarded_v5_stdlib.py --output experiments/ltx25-b70/native-cpp-block-01/guarded-v5-stdlib-01.json
```

The exact delta is [guarded-diagnostic-v5.patch](guarded-diagnostic-v5.patch).
Shared helper SHA256:
`7634e653e66a682596e2bd941017722a41b9241c785dd1fb4885bfc051c31bec`.
Harness SHA256:
`f73a16e11f0674fdaac23366a68fa6bc6ceef3c2b249557fe5159a7610b405da`.

Parent owns review and any later single native admission. There is no new CPU
compiled-block result or GPU/speed claim. Another trapped import/compilation
path remains a possible first diagnostic outcome and must be preserved without
automatic retries or policy expansion.
