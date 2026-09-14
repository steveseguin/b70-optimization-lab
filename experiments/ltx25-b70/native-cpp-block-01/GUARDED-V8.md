# Guarded v8 — narrow native CPU cache-system fallback, inactive

Prepared 2026-09-14. Implements the reviewed narrow route from
[CPU-CACHE-SYSTEM-PROPOSAL-01.md](CPU-CACHE-SYSTEM-PROPOSAL-01.md). No native
Torch/Kitchen/Inductor import, compilation, model/device execution, endpoint or
process action was performed. Encoder work retains priority; parent owns review
and any separately scheduled native admission. V7 source and its failed native
evidence are unchanged.

[The v8 helper](cpu_cache_system_policy_v8.py) installs immediately after the
frozen hardware guard and before v3 availability or v7 interface registration
capture CUDA current_device. It replaces that process-local callable with a
wrapper around the frozen trap. Before binding, every call remains a sticky
refusal. Later binding requires the exact pinned native cached
`CacheBase.get_system`, underlying code/globals and outer
`FxGraphHashDetails.__init__`, all owned by the actual source-pinned codecache
module. The native functools cache must be entirely pristine (zero hits,
misses and entries); no cache reset or repair is provided.

The one allowed ordinary RuntimeError refusal requires:

- Exact immediate `CacheBase.get_system` and immediately outer
  `FxGraphHashDetails.__init__` code-object and module-global identities.
- Python/C++ compile phase, no query arguments, no previous ordinary refusal,
  and the native function's first in-progress cache miss.
- An actual FX GraphModule and a flat list/tuple of inputs with at least one
  tensor. Only exact native Tensor, Parameter and FakeTensor classes are
  accepted as tensors, with CPU device and static integer shape/stride metadata.
  Other inputs must be simple builtin scalar/None values; opaque, nested,
  tensor-free or unfamiliar tensor inputs refuse.
- CPU-only graph parameters and buffers, checked through tensor metadata.

Every other call delegates to the original frozen Python trap, never to the
hardware implementation. The native method's existing
`except (AssertionError, RuntimeError)` catches this single exception and returns
its own empty-system fallback. All system/key/cache methods remain unchanged.
The fallback is checked against `{'hash': sha256(b'{}').hexdigest()}` according
to the separately pinned native `cache_key.py` strategy. The result is cached
once by the original function and shared across both compiled arms and stages.
Verification reads that result only after confirming an existing one-entry,
one-miss cache; these reads increment native cache hits and are explicitly
separate from omissions and compile events.

[The v8 harness](test_block_cpu_guarded_v8.py) records requested policy in durable
pre-Torch startup identity, native binding/cache state, each allowed refusal's
caller/CPU input and graph-state metadata, and per-model-call omission delta.
Only the first 64-token seed-17 Python compile may add the single system omission;
all other calls must add zero. Per-call checks, graph census and finalization
preserve hook/function/module identity and ensure successful completion requires
the unique cached fallback. Existing **four FX cache-save metadata omissions**,
two graphs per arm, native 15/6/2 operation counts, all output bytes/metadata and
repeat checks, parameter identity and numerical OPTIONS remain unchanged.
No cache-disable setting, new device registry policy, fake current-device index
or hardware-setting mutation is introduced.

This remains an explicitly modified **CPU diagnostic metadata policy**. It does
not demonstrate unchanged GPU cache identity/semantics, GPU correctness or speed.
As with prior diagnostics, unrelated native queries can still produce a guarded
failure, which must be preserved without automatic retries or scope expansion.

## Verification and review artifacts

[guarded-v8-stdlib-01.json](guarded-v8-stdlib-01.json) records **31 passing focused
stdlib/source/fake tests** (v8 cache-system and v7 registry contracts). They cover
exact caller admission, a fake native functools cache shared by both arms,
CPU parameter/buffer metadata, wrong/foreign/unbound callers, non-CPU or opaque
inputs, prepopulated/cache-cleared/corrupted results, identity mutations, inherited
trap behavior, constructor order, frozen parent sources and finalizer failure.
Source checks pin the real native exception/fallback form. No actual native
module was loaded; this is not a compiled-block numerical qualification.

Executed command:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/native-cpp-block-01/test_guarded_v8_stdlib.py --output experiments/ltx25-b70/native-cpp-block-01/guarded-v8-stdlib-01.json
```

Full runtime delta: [guarded-diagnostic-v8.patch](guarded-diagnostic-v8.patch).
Source and evidence hashes:
[guarded-v8-source-identity-01.json](guarded-v8-source-identity-01.json).
Helper SHA256:
`06b64ed60673111b6f0b8dfd220a25b3e5dbea760e178d63c225b1728986bf5d`.
Harness SHA256:
`39469089f0383f83d4232e4accad12af8f2be49dc41b2ffd30270f2013c84018`.

Final source/integration review is still required before any later native
admission. No native attempt has been scheduled by this subagent.

## Current admission status

Root read the helper and v7-to-v8 harness delta after preparation. No native
v8 attempt occurred. The separate encoder campaign later hit host OOM and an
xe fault; ROOT/FAULT.json now halts native admission. Keep this CPU compiler
proposal inactive while the encoder memory lifecycle and incident are handled.
The31 source/fake checks do not establish compiled-block or accelerator parity.
