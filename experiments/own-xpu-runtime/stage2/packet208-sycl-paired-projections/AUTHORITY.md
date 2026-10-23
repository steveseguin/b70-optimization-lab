# Packet208 native paired-projection authority

## Question and identity

This packet prepares an actual SYCL implementation of the paired Q6 projection
for compilation. Its admitted arithmetic is exactly Q6_K, K2560, expanded
variant6/split1 with3380-byte rows and output counts10240 or6144. The seven
allocation arguments are shared weight, row0 input, row1 input, row0 output,
row1 output, row0 workspace and row1 workspace. Inputs/outputs are BF16; expanded
scales and accumulation are FP32. Distinct row buffers and a shared admitted
weight allocation are part of the contract, not optional metadata.

## Outcome

[The compile-only receipt](evidence/build-compile-only.json) passed. The new
non-HOST SYCL translation unit compiled and linked with 43 repository dependency
files and 33 inherited native objects. Offline inspection found both compiled
`NativePairKernel<10240>` and `NativePairKernel<6144>` entries in the extracted
7,008-byte device bitcode, plus the linked offload image, SYCL registration and
future qualification symbol. The resulting ELF SHA256 is
`e60cdfd14a76cbb43da6be73b3e85c67e72ec811129e3cc76ce81a2f4d153e26`.

Six [offline authority checks](evidence/authority-tests.json) passed, independently
rehashing the actual inputs, objects, compiler and artifacts and reading their
ELF sections, bitcode, symbol and dependency inventories. Structural assertions
cover the reviewed ABI and ordered-queue scope. These checks do not exercise
runtime refusals or arithmetic. Neither the executable nor a device was invoked
or enumerated. Compilation does not establish native numerical equivalence,
device resource admission or speed.

## What worked

[authority-inputs.json](authority-inputs.json) binds the frozen p33 serial source
and inherited native object lineage, plus packet207's separate HOST_ONLY proof.
The raw p33 source hashes match the historical device build receipt. The p198
device link receipt independently binds the retained native p33 object.

The reference arithmetic in p33 `dense_lane<Q6_K,2560>` visits eight consecutive
elements per lane, beginning at `lane*8` and advancing by256. Each group uses the
expanded scale at `K + 4*(tile/16)` and signed quantized code. Each row preserves
the separate multiply and ordered FP32 add chain. Native p33 reduces with the
explicit subgroup selection tree of widths1,2,4,8,16 and converts once to BF16
in lane0. The new pair must keep two independent chains and the same two trees;
sharing the decoded weight does not authorize a different sum, FMA or conversion
point. Precise compiler flags and subgroup32 remain part of the build identity.

Prepared capture must retain the seven actual allocations and operation values,
not caller Matrix references. The bounded native fixture uses an explicitly
ordered queue and completed copy boundaries, not a general dependency graph or
cross-queue admission. Unsupported dependency use must refuse. Submission binds
actual pointer arguments through the runtime owner. A future fixture
must prove outputs against both original native p33 submissions and an
independent CPU p33 oracle; the new pair cannot be its own reference. Changed-row,
changed-weight, caller-metadata mutation and invalid binding/type/layout controls
remain necessary, with complete drain and original-error preservation.

## What failed or remains uncertain

The production model has70 Q6_K and2 Q8_0 GDN projection tensors. Layer2's Q8_0
pair is outside the chosen arithmetic gate; the expanded layout name alone does
not imply Q6. Packet207's tiny F32 Engine proof and synthetic Q6 HOST_ONLY proof
do not establish SYCL arithmetic, real device event behavior, device resource
limits, production Engine integration, cache/conversion semantics or speed.

An object/header hash without actual non-HOST kernel compilation is insufficient.
Conversely, an embedded device image proves compilation only, not that a device
can admit or execute it. CPU-only refusal checks must never instantiate the SYCL
backend or turn a future execution entry into implicit permission to run it.

## Evidence and patches

The source-authority map records exact input bytes and the inherited native p33
object. The new kernel/submission source and compile helper are bound by the
build receipt. The [read-only checks](tests/test_compile_authority.py) verify the
final receipt and actual compiler dependency list. Parent packets remain
unchanged. Build attempts retain their source snapshots and logs; the first
attempt stopped before compilation because the shared compile-lock helper could
not import `build_engine`. The local import alias was corrected without invoking
the native artifact.
Any future failed fixture must likewise retain its exact source, command and
diagnostic before a correction.

## When to revisit

After compile-only and source review pass, a separately admitted one-shot native
fixture can test the paired kernel against both authorities. Do not promote
compile success or host synthetic equality into a native exactness or speed claim.
