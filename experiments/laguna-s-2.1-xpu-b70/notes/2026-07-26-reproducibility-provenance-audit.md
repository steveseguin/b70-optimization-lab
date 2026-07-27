# Laguna reproducibility and native-provenance audit

Date: 2026-07-26 America/Toronto

Status: **documentation/repro hardening complete; benchmark result unchanged**

This audit made no performance claim and ran no score-bearing GPU work. The
sealed result remains:

- `102.97143559613157 tok/s` under the submitted legacy event convention;
- `101.94172124017027 tok/s` under conventional 99-interval accounting;
- 13/13 canonical-q1 token IDs and output-text hashes exact;
- LocalMaxxing `cms2ccv2d00lps201rej94pjy`, `APPROVED`.

## Gap found

The first promoted repro hashed the sibling
`vllm_xpu_kernels/libattn_kernels_xe_2.so`, but the measured
`_vllm_fa2_C.abi3.so` contains an absolute RUNPATH into:

```text
/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/build/temp
```

With the historical launch environment, `/proc/self/maps` proved that the
loader selected the library from that external build tree. It happened to be
byte-identical to the sibling file, but the preflight did not prove that.
External drift or deletion could therefore change or break the runtime while
the old preflight still passed.

Importing `_xpu_C` also loaded four unpinned helper DSOs:

- `libgrouped_gemm_xe_default.so`;
- `libgdn_attn_kernels_xe_2.so`;
- `libmqa_logits_kernels_xe_2.so`;
- `libmhc_kernels_xe_2.so`.

Finally, editable package metadata supplied `xpumem_allocator` from a separate
DeepSeek kernel tree. Its source and binary were compatible, but neither its
origin nor hash was part of the initial promoted contract.

## Reconstructed native provenance

| Runtime object family | Observed source commit |
| --- | --- |
| final router/workspace source and `_moe_C` | `6f9dd3c3a7b1b677a992ca4f431a968408f9c816` |
| `_vllm_fa2_C` and `libattn_kernels_xe_2.so` | `906190641d708b8028018c5dde653e265c835348` |
| `_C`, `_xpu_C`, grouped GEMM, and transitive helper DSOs | `4772f727590c51b72add79350b913d098cf67872` |
| `xpumem_allocator` | `18a44f440ca3ac2006d5ba19cd12ccca0a0c9982` |

The supplemental `906190641` bundle and combined patch are now tracked beside
the final vLLM and kernel snapshots. The earlier `4772f727` and `18a44f440`
commits are present in the main kernel bundle's history.

## Hardening applied

The standalone repro now:

1. puts the pinned kernel package first in `LD_LIBRARY_PATH`, overriding the
   extension's absolute RUNPATH selection;
2. hashes four Python extension modules, six helper DSOs, and
   `xpumem_allocator`;
3. imports every module without allocating an XPU and checks its real origin;
4. inspects `/proc/self/maps` and requires each helper DSO to map only from the
   pinned kernel package;
5. records the runtime-verification JSON in every new run and binds its hash
   into `identity.txt`;
6. tracks the full observed runtime/package/host identity;
7. tracks a release-only 32-file model manifest and download-at-revision
   helper;
8. embeds the sealed benchmark, exactness report, server log, identity,
   service environment, metrics, cleanup, and every idle snapshot;
9. makes sealed-record verification fail if that raw evidence is absent;
10. validates a new run's exact identity, selectors, environment, runtime
    maps, cleanup keys, idle phases, token/text equality, topology, treatment,
    metric math, and a conventional performance floor.

## Reproducibility claims

Three evidence classes are intentionally separate:

- **portable sealed-evidence audit:** recomputes and verifies the historical
  claim without a GPU;
- **artifact-exact lab replay:** requires the originating host's
  byte-identical venv and native files;
- **source-equivalent rebuild:** restores all sources and models but produces
  a new binary environment that must pass the full gate.

The original single monolithic native build invocation was not sealed.
Consequently, a clean rebuild is not called bit-identical merely because it
uses the same Git commits. The tracked `BUILD.md` provides the observed
toolchain and standard source-equivalent build entry point while preserving
that limitation.

## General rules for future model work

1. Hashing a sibling DSO is not loader provenance. Record `DT_NEEDED`,
   RUNPATH/RPATH, `LD_LIBRARY_PATH`, module origins, and actual mapped paths.
2. Pin transitive native dependencies, not only the Python extension directly
   imported by the model.
3. Treat editable package metadata as advisory. Git HEAD, `PYTHONPATH`,
   module origin, file hash, and mapped object identity are the runtime facts.
4. Keep sealed-evidence verification portable and fail closed when evidence is
   missing. “Not mounted” is not PASS.
5. Separate exact artifact replay from source-equivalent rebuild. Compiler
   identity alone does not promise bit-identical native output.
6. Model manifests should contain immutable release payloads, not cache locks,
   metadata, or incomplete downloads.
7. A reproduction validator must test both semantics and performance.
   Correct-but-slow is useful evidence, but it is not reproduction of a speed
   headline.
8. Record exact cleanup keys and pre/post idle evidence; empty or partial
   status files must fail.

## Pointers

- [standalone repro](../../../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md)
- [build and reproducibility tiers](../../../repro/laguna-s-2.1-int4-b70-102tps-20260726/BUILD.md)
- [source snapshot index](../../../patches/laguna-s-2.1-xpu-b70/README.md)
- [qualified result packet](../../../results/laguna-s-2.1-int4-b70/README.md)
- [campaign transfer ledger](2026-07-26-campaign-transfer-ledger.md)
