# Packet53b decisions

Persistent expert arms are closed by [packet53](../packet53-expert-order/DO-NOT-REPEAT.md).
Never substitute V4 for the production timing baseline. Never combine each
owner's independently selected winners. Do not remove the per-chain K check:
K640 and every Split4 K2560 chunk end with unequal lane lengths.

The production adjacent SG32 tree and Split4 tree are part of the identity.
No free-order sums, FMA contraction, changed precision, cached responses or
new oracle. A device result is pending until E1/E2 and T1/T2 pass.

## CPU register decisions

- Paired V8/V16 at128 GRFs spill2432/4352 bytes in initial offline screening.
  Not admitted. Bounded two-chain scheduling and scalar unpack attempts also
  spill; retained under evidence-cpu.
- The experimental256-GRF kernel property emits SPV_INTEL_maximum_registers,
  which installed ocloc refuses. Do not send this unqualified module to a GPU.
- Separate gate/up subgroups preserve every chain/tree and eliminate the
  V8/V16 spills in screening. Final report binds the production-pitch build.
- Do not call packet53's aligned16 expert pitch the packet49c compact pitch.
  This packet uses packet49c's actual820/360-byte rows for both arms.
- `dispatch-p45.json` is not the active control map. Packet49c uses the
  SPEED6 map, byte-identical to packet51's registered baseline map.
