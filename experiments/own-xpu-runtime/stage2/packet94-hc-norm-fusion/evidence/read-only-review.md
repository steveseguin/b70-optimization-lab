# Read-only review of packet94

The independent read-only review found no concrete arithmetic, synchronization
or dispatch defect. It checked that K/4 equals H, original trees and BF16 edges
remain, workgroup0 is the sole norm/scratch writer, enabled other workgroups
read only residual/gain, and disabled/error/invalid-position behavior retains
production semantics. Gate/mix and packet90 cache composition remain separate.

It found one proof gap inherited from packet90: native-plan and census archive
hashes were recorded but not rechecked by seal.py or bound into final sources.
Packet94 now checks both per-run hashes at sealing and includes all twelve
archives in every view's sealed sources. No frozen packet was changed.
Device parity and speed still require the coordinator's screen.
