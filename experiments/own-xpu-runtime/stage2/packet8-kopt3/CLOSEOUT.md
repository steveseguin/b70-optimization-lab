# Round 3 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

October 11, 2026, own-runtime stage 2, Unsloth UD-IQ3_XXS quantized compressed
version; exact production census and round-2 receipt hashes in [dispatch.json](dispatch.json).
Can block-local decode sharing, codebook staging and measured shape dispatch
improve the card-3 diagnostic? CPU-only icpx 2026.0.0 preparation on steve-b70s.
No GPU, server, driver, power, memory setting or device ownership was changed.

## Outcome

CPU preparation complete, device outcome pending. [Build receipt](build-receipt.json)
records exact scalar/row comparisons, fresh process repeat and compiled SYCL
programs. Neither CPU equality nor forecasts establish device speed, complete
model parity or a qualified runtime. No round-3 candidate is promoted.

## What worked

Four separately named constant/SLM and SG32/split4 candidates share block and
subblock metadata while preserving the round-2 arithmetic tree. Signed integer
decode removes finite-path sign multiplication. All production tensors have
an unambiguous census-bound operation mapping. Gate/up uses one ten-expert
launch with shared read-only bindings; down stays a separate launch. Offline
bitcode-to-SPIR-V inspection works without loading a device runtime.

## What failed or remains uncertain

Direct `-S` and `-S -emit-llvm` are rejected by this compiler. The installed
system spirv-dis cannot read decoration 5940; use the bundled translator's
text mode. Intermediate assembly is not Xe ISA, register counts or occupancy.
Special-value CPU tests initially exposed a NaN sign difference when combining
sign arithmetic; exceptional scales now retain the original scalar equation.
Device exactness, new bandwidth, SLM initialization/bank conflicts, real-layer
input readiness and full-model output parity all remain open. IQ4_XS has only
CPU format coverage because it is absent from production and packet-2 device
admission. A true FMA would change the oracle, so contraction remains disabled.

## Evidence and patches

[README](README.md), [source census and forecasts](analysis.json),
[offline compiler receipt](assembly-receipt.json), [build receipt](build-receipt.json),
[decode](decode.hpp), [kernels](kernels.cpp), [reference](reference.hpp),
[dispatch](dispatch.json), [negative index](DO-NOT-REPEAT.md).
The earlier round-2 receipts remain at their original paths. Rebuild with
`validate.py --keep-build` to restore ignored binaries/fixtures/assembly;
CPU scratch is deleted by the normal validator. No device receipts exist for
this round, and no full raw GPU artifact is implied.

## When to revisit

The coordinator runs the README's exactness window, then timing window on
card 3 after independent admission. Preserve the evidence even if SLM loses.
Require another fresh owner/window and matching exactness before accepting a
speed winner; keep the old shape choices until then. If decode-only savings
are small for Q6/Q8, examine dependency-correct launch scheduling and compiler
register pressure using the new receipts, rather than reopening wide rows.
