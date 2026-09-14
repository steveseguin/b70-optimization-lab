# Guarded v4 CPU cache-metadata policy — import refusal recorded

The later single native diagnostic stopped before model/compile execution at
Comfy's unconditional import-time device-count probe. Both GPU backends stayed
uninitialized and the LTX application stayed unchanged. See the
[native attempt](guarded-v4-native-attempt-01.md). Do not rerun v4 unchanged;
the source preparation below remains historical evidence.

Prepared 2026-09-14. The source-only successor addresses the direct Triton NVIDIA
activation path identified in [GUARDED-V3.md](GUARDED-V3.md). No native dependency
was imported, and no CPU compilation, model execution, endpoint or device action
was performed while preparing v4. Parent owns any later native admission.

[cpu_metadata_policy_v4.py](cpu_metadata_policy_v4.py) replaces only the
process-local `torch.utils._triton.triton_backend` callable. It never calls the
original function. Installation precedes Kitchen/Inductor imports, initially
refusing every call with the existing sticky BaseException mechanism. After
codecache import, it binds the precise original static
`FxGraphCache._save_graph` function, its code object and owning globals. Binding
requires code-object equality with a stdlib compilation of the full pinned
source; that compilation does not execute dependency code. Source SHA256s also
pin the Triton helper, codecache, output_code and OrderedSet implementation.

An ordinary `CpuOnlyCacheMetadataUnavailable` exception is allowed only from the
bound function's exact code object and globals, with plain instance fields,
`extern_libs_key is None`, and `device_types` exactly the bound, source-pinned
native OrderedSet class containing only `cpu`. Its `_dict` slot must be an exact
builtin dict with exact string keys; arbitrary iterators, subclass collections,
and properties are not called. The original `_save_graph` ordinary exception
handler catches this exception and continues graph serialization. Its source,
graph guards and cache-saving code remain unchanged. The backend's original
Triton driver selection and direct NVIDIA ctypes calls are never entered through
this hook.

Every other caller, unbound query, argument, non-CPU graph, prior extern-libs
value, identity mutation or fifth omission halts via sticky BaseException. In
particular, no cache-hit metadata caller is whitelisted. Existing device-count,
initialization, property and stream traps remain unchanged. This does not claim
to intercept arbitrary native driver access elsewhere; any later diagnostic
result must be assessed with its traces and host evidence.

The [new harness](test_block_cpu_guarded_v4.py) shares this policy and v3's pure
False CUDA/XPU availability functions across eager, Python boundary, C++ boundary
and repeat arms. It records both requested policies in the pre-Torch startup
receipt, installed binding identities, every permitted metadata omission, and
per-call omission deltas. The original v3 availability description remains
historical; the additional explicit v4 metadata policy is the composite
successor's treatment of that outstanding bypass.

Cold first-stage calls must have one omission per new graph; eager and warm
calls must have zero. Exactly four omissions are required across both stages
and both compiled arms. The 15 RMS / 6 sigmoid / 2 GELU counts, original compiler
options, numerical arithmetic, both-video/audio byte parity and repeat gates,
parameter identities, graph counts, fault checks and isolated cache requirements
remain. Finalization rechecks both metadata and availability/trap identities;
a swallowed failure or tampering cannot leave `passed=True`.

[guarded-v4-stdlib-03.json](guarded-v4-stdlib-03.json) records **39 passing
stdlib/source/fake-module tests**, with no Torch, Triton or Kitchen module loaded.
They cover source pin/code extraction, exact caller ownership, CPU metadata,
foreign iterables, retained traps, sticky failures, finalizer tampering, source
ordering and numerical helper identity. These are not native compiled-block
parity tests. The initial 35-pass and intermediate 39-pass receipts and their
source snapshots remain preserved. Review deltas are in
[guarded-v4-review-hardening.patch](guarded-v4-review-hardening.patch); the full
v3→v4 runtime delta is [guarded-diagnostic-v4.patch](guarded-diagnostic-v4.patch).
All source/receipt hashes are in
[guarded-v4-source-identity-01.json](guarded-v4-source-identity-01.json).

Executed stdlib test command:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/native-cpp-block-01/test_guarded_v4_stdlib.py --output experiments/ltx25-b70/native-cpp-block-01/guarded-v4-stdlib-03.json
```

Proposed parent-owned check-only command (not executed by this subagent; both
paths must be new):

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/native-cpp-block-01/test_block_cpu_guarded_v4.py --check-only --output experiments/ltx25-b70/native-cpp-block-01/guarded-v4-source-check-01.json --evidence-dir /mnt/fast-ai/bench-results/ltx25-baseline-20260913/native-cpp-block-cpu-guarded-v4-01
```

Removing `--check-only` is a separately scheduled native diagnostic, not a
reproduction command authorized by this note. It could still refuse before CPU
compilation at another trapped query; preserve that first result without retry
or automatic policy expansion. Source-code equality will also first encounter
actual imported functions at native admission. No CPU compiled-block success,
GPU correctness, GPU-query completeness or speed claim follows from this note.

Frozen harness SHA256:
`35924bf2f856afa57cb6f29c004b0dac56cf9d50764de8a6309dd432043a2a00`.
Frozen metadata policy SHA256:
`4fffdedf7d109cc14456aef37031e7471138a9c19c840596efb1e3197e972a80`.
