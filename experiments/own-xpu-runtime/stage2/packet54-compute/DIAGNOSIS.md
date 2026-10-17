# Packet54 compute diagnosis

The controls match packet49c SPEED6, including its selected packet51 route.
This is source analysis of prior measurements, not new timing. Launch gaps
and bandwidth-limited dense GEMVs are closed as levers for this packet.

| Class | Prior M1 time | Conditional byte floor | Changed work and honest bound |
| --- | ---: | ---: | --- |
| route | ≈24.6 µs | <0.01 µs, distinct bytes only | Same 512 deterministic exp calls and 262144 comparisons. Share normalized inputs among four ranks; distribute exp across more workgroups. Stages 0/4 remain, leaving <≈17.9 µs planning opportunity before positive remaining work. Component measurements are from different retained runs. |
| GDN recurrence | 35.938 µs | ≈5.6–5.7 µs at 555–570 GB/s | 6144 SG32 state rows repeat head normalization and decay. Share exact head values over four/eight rows. Prediction/update/output dependencies stay. Byte-only headroom ≈30 µs is an optimistic ceiling. |
| HC inject/mix/norm, both sides | ≈60.6 µs | ≈1.1 µs for distinct inputs/outputs/weights | Keep inject. Norm sharing was rejected on exceptional production bytes. The eligible mix arm handles four independent dimensions. The old ≈19.3 µs norm subtotal bounds its own opportunity; mix retains every sigmoid. No claimed gain for inject. |
| FFN combine | 11.2 µs | ≈0.084 µs | Proposed four-output factor sharing was closed by an actual-production BF16 NaN mismatch. Keep production and credit zero saving. Source-call reduction alone did not establish byte identity. |

Byte floors use prior dense bandwidth only as a conditional reference, not a
universal device limit. Cache residency and repeated loads change actual
traffic. There is no measured instruction issue rate for the compensated
math, precise divisions, shuffles or local-memory accesses, so **no numerical
compute-time floor or achieved occupancy percentage is invented**. Geometry,
counts, barriers and serial chains are derived from source below. All new
speed results require the coordinator's fresh paired windows.

- [Route source diagnosis](DIAGNOSIS-ROUTE.md): four stages, occupancy, local
  cache/divisions, normalized ties and why one-workgroup fusion is excluded.
- [Recurrence source diagnosis](DIAGNOSIS-RECURRENCE.md): exact four-term
  leaves, already register-resident state, head sharing and added local traffic.
- [HC and FFN source diagnosis](DIAGNOSIS-HC-FFN.md): exact80-leaf norm tree,
  deterministic sigmoid cost, unchanged inject and packet46's occupancy loss.

The packet46 norm fusion reduced repeated work but confined each stream to
one workgroup and serialized the inverse. Its norm subtotal worsened from
19.272 to35.6765 µs. The proposed norm arm kept the two-stage partial buffer and 80 output
subgroups, but failed actual-production exceptional bytes and was closed.
The eligible mix-only arm leaves normalization unchanged.

Detmath is packet17's exact implementation: exp has13 coefficients and12
compensated Horner steps after range reduction. Explicit FMA residuals inside
that established algorithm remain; ordinary expressions compile with
`-fno-fast-math -ffp-contract=off`. No native/host fast-math substitution,
reassociated tree, compressed state, altered BF16 cast or new oracle.
