# Packet117 HC sigmoid scheduling — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Does moving independent sigmoid products onto the paired gate rows' existing
subgroups remove a material part of the HC gate event while preserving every
output byte? The target is the lab's quantized Flash-Next IQ3 lane,
`iq3-p49-split32-v1`, on B70, prepared October 18. The micro copies packet110's
synthetic full-layer fixture at context 128. The one-load bracket inherits
packet111 after 111r, with only `hc_gate=production|p117` changing.

## Outcome

CPU preparation passes. Both GNU and Intel pass sixteen HC cases twice,
including mixed NaN/Inf, against each compiler's unchanged production. The
copied complete-layer host harness passes 4,736 comparisons. The device binary
compiles, both linked HC kernels use 128 GRFs without spills, and both fresh
micro proposals pass temporary queue planning. The v5 build, selected-view
startup, reset, IPC, policy, limit and seal checks also pass.

No device work was run in this preparation. Device equality and the <=0.70
micro time gate remain unmeasured; v5 launch stays conditional on both fresh
micro processes passing every site/layer/order cell. There is no model speed
or promotion result.

## What worked

The source audit separated weight conversion from the four serial software
sigmoids included in the reported gate event. Production chains, loads,
geometry, per-row reduction and final ordered addition stay intact. The
candidate runs finite independent products in parallel and preserves the
original scalar expression for exceptional products. Native image inspection
shows no HC spill penalty. Source-bound seals and isolated micro qualification
prevent the v5 wrapper from accepting stale or colliding imported gates.

## What failed or remains uncertain

The initial unconditional product-array path changed a GNU NaN payload in the
first mixed-NaN test; the original eight fixtures missed it. Its source and
bytes are retained. The original production also differs between compilers
on three exceptional fixtures; same-compiler exact equality and repeats pass,
without tolerance or canonicalization.

The first micro compile lacked a kernel-guard include. Later source-change
and unrelated generated-file checks correctly refused stale build receipts.
The checked mirror now preserves original `__FILE__` resource paths, and the
native source manifest comes from compiler dependencies. A symlink to the
frozen RoPE table failed the wrapper's identity-path policy; the byte-identical
packet-local copy is retained explicitly. None of these failures ran a device.

The candidate's actual GPU NaN payload selection, time, and full-model effect
remain unknown. Linked allocation metadata is not measured occupancy or DRAM
bandwidth. The full micro and subsequent unchanged-target model gates decide.

## Evidence and patches

- [Work note and exact source rationale](../../../../notes/2026-10-18-own-runtime-packet117.md)
- [Candidate kernel](hc_gate.hpp)
- [GNU/Intel byte receipts](evidence/cpu-byte-identity.json)
- [Complete-layer host receipt](evidence/cpu-layer.json)
- [Linked HC allocation audit](evidence/hc-register-summary.json)
- [Rejected unconditional source and bytes](evidence/rejected-unconditional-products/)
- [Temporary micro plan](evidence/micro-queue-plan.json)
- [v5 checks and conditional plan](v5/README.md)
- [Retention and rebuild](RETENTION.md)

## When to revisit

The coordinator runs the two proposed fresh B micros. Advance only if each
meets exact bytes and <=0.70× for both HC sites, both layer types and both
orders, with clean drained owners. Otherwise retain the failure and close
this mechanism without changing the runtime or weakening the gate. A micro
pass admits the prepared v5 bracket; it does not qualify a record.
