# GSQ packed Engine integration

This additive materialization uses the actual P195 executable's P194v5 source closure, rather than the older P195 top-level Engine source. It implements an explicit `--gsq-packed` mode for the downloaded two-shard SC117 model. It does not establish full-model native correctness or throughput.

`prepare.py` binds the P195 native source manifest, relocates physical includes into a private tree, applies the independently tested loader admission and packed decoders, and records every source and generated-file hash in `preparation.json`. `overlay.patch` preserves the complete transformation. No frozen source is modified.

The actual primitive graph remains unfused. Five newly supported packed formats use the separately qualified native-format facade; existing formats use generic packed kernels with the original explicit gather and mixture operations. Original non-GEMV primitive implementations remain in use. Exactly one storage exception is retained: the full expanded Q6 output head, using p33 variant 6 for target and MTP. The admitted control names use exact F32 upload, including widening the single F16 PLE control. Model tensor descriptors remain authentic.

Real-mode admission requires context 4096, explicit target split 24/24, and draft rank 0. The MTP head covers the full 248,320-token vocabulary and records no old calibration hash. Native and Host builds use the same explicit baseline selection defaults and original rank/controller protocol, private draft state, snapshot and rollback implementation. The historical draft receipt's `head_scope` prose is unchanged and imprecise for the new private Q6 head; allocation and prefix fields identify the actual path.

## Completed CPU evidence

- `evidence/header-check.json`: authenticated both real shard header prefixes and parsed the actual loader/directory, then built the shared real Engine graph: 1,224 tensors, 1,869 launches, 785 dense GEMVs and 144 routed GEMVs. No Device or tensor payload read. This receipt binds the earlier preflight source revision explicitly.
- `evidence/full-host-build.json`: complete GNU build from 32 translation units, with no reused objects. Two earlier build recipe failures are retained: a SYCL-only TU in the Host list, then the absent historical fixture-mode defaults header. `evidence/host-build-attempts.json` indexes them.
- `evidence/host-lifecycle.json`: four synthetic Host owners, two rank pairs using the actual C++ native controller. Target-only and MTP each emit four identical tokens and exact final target state bytes. MTP makes three guesses, two hits and one miss with rollback/redo. All owners close cleanly. This tests synthetic arithmetic and simulated Host backend events, not new-model native acceptance.
- `evidence/host-native-source-delta.json`: after that Host proof, independent review corrected one native-only generic routed call from `(routes, output)` to `(output, routes)`. The Host branch is unchanged. `host-retained-source-map.json` resolves the three historical paths whose bytes differ from the current materialization.
- `evidence/independent-execution-source-review.json`: independent review of the corrected source closure, rank initialization, control upload, packed dispatch and MTP wiring.

## Native compile result

`evidence/full-native-build.json` records the first native attempt passing compile, link and offline inspection: 40 fresh objects, 195 dependency files and 404 source bindings. Binary SHA256 is `16ce5bbda43e9d3d39c2446fc3037ea352d345f62161453f1ab0539330046ea2`. The five packed-format kernel entries and actual Engine/MTP symbols are present. The executable has not been invoked by this implementation task.

The separate `sycl-post-link` inspection of the entry TU's unlinked device bitcode emitted unresolved `fmaf` and `sqrtf` warnings; the complete executable link passed. `evidence/native-offline-notes.json` preserves that distinction. Device execution, whole-model initialization, numerical acceptance and native math-library resolution remain separate qualification gates.

## Rebuild boundaries

`build_full.py --mode host --plan` and `--mode native --plan` are read-only command previews. Explicit `--build` rebuilds all affected translation units, serially under the existing compile coordinator, with strict floating-point flags and compiler/source/dependency/object hashes. It does not invoke the resulting executable. Native builds additionally inspect the offload image, all five new packed kernel entries, linked symbols and the public entry disassembly. The public executable refuses without the explicit new-mode flag; that flag alone is not operational admission.

The reviewed build environment is GNU or the pinned oneAPI 2026.0 compiler, nice 19 on CPUs 8–15 and 24–31, thread variables set to 2, 4 GiB address-space limit, and a 250 MiB write forecast above the 27 GB root free-space floor. Root owns all native execution and service coordination. These are host-specific research builds, not a portable release package.

Each build attempt retains commands, compiler output, source snapshots and a receipt under ignored `build/`. Small failure recipes/logs and the source patch are retained in `lineage/`; no model payload or large generated private tree belongs in Git. The parent source hashes plus transformation reconstruct the generated inputs. Failure evidence is not silently replaced by later success.
