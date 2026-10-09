# Explicit host pointer MoE candidate — CPU preparation only

This candidate implements the held proposal in the
[attempt-7 fault analysis](../../notes/2026-10-08-attempt7-gpu-fault-analysis.md).
It is **not applied** to `../overlay/`, installed in a runtime, or included in
`../overlay-manifest.json`. No card, native compiler or model was used here.
The fault's cause remains a hypothesis.

`explicit-host-pointer.patch` is a reviewable diff against the two existing
pinned overlay modules; `modules/` contains their complete candidate copies.
The original placement module SHA256 is
`4e1e3eaa3016ce3c364db64fde8294073f8575e0f06590a50c267a974988a2c7`;
the original fused MoE module SHA256 is
`f5252f843722ea91149b1e93c60e67318957d552ff1cf8014d15909ef30b5542`.
The patch paths are relative to an overlay root. This packet does not grant
permission to apply it or refresh the active overlay's hashes.

The allocator and native UVA helper are unchanged. At weight creation, the
candidate adds two device tables indexed by logical expert: an int64 local
row index and a uint8 host/resident selector. The production signed-offset
table is retained as a diagnostic oracle but is no longer passed to the MoE
kernel. The launch passes both resident and host UVA tensors as actual pointer
arguments. The kernel selects one base first, then adds the local row offset
inside that allocation. Both w13 and w2 use this shared invocation path.
An absent or incomplete candidate table set refuses launch, rather than using
an old table with the new kernel contract.

The host pointer participates in `tl.where` and the resulting pointer is used
by the existing weight loads. The K/N addressing, negative-expert sentinel,
scales, FP8 loads, dot products and stores are unchanged. The local row is
int64; the existing 256-element alignment hint is retained only after the
row-stride validation. CPU host and UVA pointer/dtype/shape/stride equality
is checked at creation. Immutable pointer/shape/stride/dtype/device facts for
all three tensors are saved and checked immediately before every invocation;
postprocessing restores those facts and both new tables. These checks do not
read device table contents or prove the contents cannot later be mutated.

Run the CPU tests from the repository root:

```sh
/home/steve/.venvs/ltx25-baseline/bin/python -B -m unittest discover -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-fix-hostptr -p 'test_*.py' -v
```

**9 tests passed, zero skips.** NumPy emulation checks the production signed
offset formula against selected-base addressing for every expert and every
matrix row in both registered placement maps, all four ranks, all 48 layers,
and both w13/w2 shapes. It covers signed positive/negative/wrapped deltas,
one- and two-byte elements, an interior slab view, and every byte of a tiny
synthetic gather. It also checks metadata restoration, mutable-storage drift,
unchanged K/N and FP8 source, source pins, patch/copy consistency and parsing.
These use small CPU arrays and no Torch, Triton or vLLM runtime imports.
A separate read-only addressing review found no CPU-scope blocker and confirmed
the modulo-2**64 reconstruction, alignment guard and unchanged arithmetic.

A CPU address-equivalence pass does not certify launch-queue context, host-USM
registration, residency, driver/UR behavior, native pointer selection codegen,
FP8 kernel correctness, output identity, performance, TP4, PLE or startup.
The one-card direct-pointer probe is a separate later experiment, not an
automatic follow-up to an indirect-probe failure. Before applying this fix,
the coordinator needs the authorized clean-boot/health/fault-watch conditions,
raw-byte direct gather evidence, native IR review showing both pointers remain
used, and then the lane's kernel/output and fresh-runtime repeat gates.
Any new fault stops submissions; never chain another probe or full model load.
