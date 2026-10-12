# Packet44 seal audit

`seal_context.py` is implemented and syntax checked. **The seal has not run.**
The build entry now calls it instead of the inherited packet38 seal. A missing,
failed, stale-binary, stale-source or incomplete required gate refuses the final
seal; partial gate campaigns cannot produce `passed: true` for this packet.

Independent command inspection found required precision flags on both compile
and link commands in all four CMake configurations:

| Configuration | Compile commands | Link commands | Precision flags |
| --- | ---: | ---: | --- |
| GNU host | 47 | 11 | no fast math; FP contraction off |
| Intel host | 47 | 11 | no fast math; FP contraction off |
| ASAN/UBSAN host | 47 | 11 | no fast math; FP contraction off |
| Intel device | 35 | 5 | above plus IEEE denormals and precise FP32 division/square root |

The six standalone native-controller/mailbox binaries compile and link in the
same recorded invocation. All six include `-fno-fast-math` and
`-ffp-contract=off`. ASAN/UBSAN and TSan variants explicitly carry their sanitizer
flags. The seal rechecks the commands, source hashes and actual binary hashes.
The observed kernel-size receipt covers 410 captures, maximum 752 bytes, with
the 1,025-byte negative compilation rejected. Argument checks report 16 passes;
prepared invalidation reports 15 ASAN/UBSAN checks. The final seal re-reads the
linked image's capture-size symbols so an old size receipt cannot qualify a new
image. No device image is executed by the seal.

`build.py` now emits `build-{mode}-receipt.json` immediately after each successful
build. These bind the compiled C++ dependency closure, CMake/source generators,
RoPE, binaries, compile commands and link files. Unrelated Python and document
edits do not invalidate compilation. Wrapper/source files are independently
hashed into the final seal. All four final incremental builds must emit these
receipts after the last compiled-source change.

The active wrapper receives genuine context-specific fixture/draft maps, the
current input hash, full memory plan, artifact hashes and official draft manifest
hash. The official tensor identity is read from immutable packet38 evidence;
its explicit repository path and hash are included in the source bindings.
There is no copied old gate pass. A real new aggregate `cpu-tests.json` is emitted
only when all required gates validate. The obsolete standalone fixture entry is
disabled; no invented legacy memory census or fake host-binary alias is supplied.

The fixture aggregate must contain six exact nongemv arithmetic arms, two linked
arithmetic arms, three GNU K2 validation arms and one GNU validation-only arm.
It also must contain successful K2-selection/admission and storage regression
checks. Counts follow the registered finite shape lists: nongemv 170 checks at
256/4,096, 179 at 32,768, before the separately reported adapter checks. Validation
arms are never accepted as arithmetic exactness evidence.

The model gate must contain exactly the 38 required current cases: three suite
prompts × three capacities × two compilers; four development modes × two
compilers; and three rollback modes × two controllers × two compilers. The seal
checks token/fixture equality, archives, current binary/source identities and
the discarded speculative half across position 32. Six CPU draft arms must
match between compilers and match retained valid-prefix rows across capacities.
All completed device windows remain pending after a successful CPU seal.

The completed support, selection, full fixture, ASAN boundary and draft
authentication validators have now been exercised against the current binaries.
They pass. All three mini/MTP variants and the 1,109-case actual-Engine native
controller gate are mandatory seal inputs, as is the exact current memory-plan
hash. The real-model capacity matrix and six draft capture arms remain pending;
the final seal has not run.

The draft proof requires 63 frozen packet38 valid-prefix files per new arm,
across six arms. The shipped full-byte archive is verified against the original
sealed fixture map. The embedded capture execution and input table hashes must
match, and the packet44 input receipt must name that same source input receipt.
The final seal rechecks these links and hashes the baseline JSON and archive.

The negative 1,025-byte capture diagnostic is retained as
`oversized-capture.log.gz`. Its receipt binds compressed and original SHA256,
byte count and the expected compiler rejection. The original 1,119 bytes were
round-trip checked before deleting the raw log. This was an evidence-format
change; it does not claim another compiler execution.
