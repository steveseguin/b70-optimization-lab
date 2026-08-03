# Laguna INT4 compile-time affine-state static-screen preregistration

Date: 2026-08-03 America/Toronto

Status: **preregistered before AOT; compile-only and not yet run**.

This is a distinct source successor to the closed `a0c7ae628ff1` candidate.
It authorizes one new offline BMG AOT compilation and static inspection only.
It does not authorize running the emitted executable, importing or probing an
XPU runtime, loading a model, touching a service, resetting a device, or using
privilege. The PCIe/NVMe corrected-error quarantine remains unchanged.

## Prior result and single change

The first affine candidate compiled selector-true at 369 instructions, but it
failed the frozen gate because:

- selector-false was contaminated at 398/346/10 rather than the archived
  370/320/9 control identity; and
- selector-true had sync metric 10 plus four `sync.allrd` operations rather
  than the archived control's sync metric 9 and zero `sync.allrd`.

The source cause of selector-false contamination was unconditionally declared
affine tensor/copy/prefetch state. Candidate `1ef527526e8c` moves every affine
object into the true branch of one compile-time lambda and returns an empty
tuple for selector-false. Affine uses remain inside true `if constexpr`
branches. It does not change the N64 x K32 record format, packed nibbles, BF16
scales, K order, prefetch distance, arithmetic, DPAS, output, or MXFP4 fallback.

Candidate identity:

- source tree:
  `/home/steve/src/laguna-xpu-kernels-int4-affine-state-20260803`;
- branch: `experiment/laguna-int4-affine-state-20260803`;
- base / closed first-affine commit:
  `a0c7ae628ff1249c3fb105220b4dd664b960ad95`;
- candidate commit:
  `1ef527526e8ca18e7c04dc9bb8b23020e6f8dec2`;
- patch snapshot:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-isolate-affine-tile-record-state.patch`.

Before AOT, 5/5 static source guards, Ruff, `git diff --check`, the header-only
oneAPI 2025.3 syntax check, and a full matched-probe `-fsycl -fsyntax-only`
instantiation all passed. None is an ISA, correctness, performance, or memory
result.

## Frozen compile-only action

Run the same two-kernel K256 probe exactly once into this new, nonexistent
output root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-state-1ef527526e8c-20260803T013000
```

The frozen command is:

```bash
LAGUNA_IGC_GRF_MODE=128 \
LAGUNA_XPU_DEPS_TREE=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731 \
LAGUNA_IGC_PROBE_SOURCE=/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/igc_int4_tile_record_probe.cpp \
LAGUNA_IGC_KERNEL_PATTERN=LagunaInt4TileRecordProbe \
experiments/laguna-s-2.1-xpu-b70/tools/run_igc_int4_mainloop_probe.sh \
  /home/steve/src/laguna-xpu-kernels-int4-affine-state-20260803 \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-state-1ef527526e8c-20260803T013000
```

Dependency source remains
`cd763790ad2f74d7294435ecf77682bac0062c3a`. The output executable must never
be invoked.

## Frozen pass/fail gate

Use `tools/analyze_laguna_int4_tile_record_aot.py` unchanged. It must find
exactly one `ILb0EE` selector-false assembly and one `ILb1EE` selector-true
assembly.

Selector-false must recover the archived ordinary control identity exactly on
the frozen anchors:

- 370 total and 320 ALU instructions;
- sync metric 9, with zero `sync.allrd`, nine `sync.nop`, and one `sync.bar`;
- 2 DPAS and 33 unpredicated multiplies;
- GRF128;
- the archived memory/send/sync opcode histogram; and
- no executable scratch or spill operation.

Normalized full ISA must also match the archived control, allowing only the
known hash-seed/header and terminal hash-sentinel differences. A metric-only
match cannot waive a normalized-body mismatch.

Selector-true passes only if all of these hold:

1. at most 378 total instructions;
2. 2 DPAS, 33 unpredicated multiplies, and the same normalized arithmetic
   body/order as control;
3. sync metric 9, zero `sync.allrd`, nine `sync.nop`, one `sync.bar`, and exact
   archived-control memory/send/sync opcode histogram;
4. GRF128 and no executable scratch/spill;
5. steady future-prefetch block no longer than control's eight instructions;
   and
6. no recurring multiply-by-1152 or copy-descriptor materialization in the
   K/prologue traversal.

The analyzer supplies the automated numeric/cardinality checks; normalized
full-ISA and hot-block comparisons remain explicit manual gates. Fresh
selector-false failure closes this successor as an isolation failure;
selector-true failure of any condition closes it as an affine-state static
loss. Do not use the contaminated 398-instruction kernel as a control, do not
relax a threshold after inspection, do not retry this immutable commit, and do
not time either failure. A full pass would establish only an acceptable ISA
shape and would not authorize device work.

## Unchanged downstream stops

The full record representation is 15.1875 GiB/rank. Keeping original weights
while replacing only the transposed-scale clone still grows persistent memory
by 13.5 GiB/rank. Duplication remains a hard no-go; any eventual integration
requires a separately proven replacement design and separate device-safety
authorization.

The protected 125.461973 conventional tok/s record remains unchanged.
