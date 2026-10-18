# Packet99 IQ4 byte-pair table closeout

Question: can a small exact byte-to-two-level table remove production IQ4_NL
bank-selection decode without changing FP32 values or sums?

Identity: packet97 source copy; `p99::Kernel<IQ4_NL,640,4,false>`, wide64,
`iq3-p49-split32-v1`. `p99_expert.hpp` keeps the source. The table packs all 256
code bytes into 128 uint32 words (512 bytes), filled once per WG64.

Outcome: CPU exactness passes GNU and Intel, including all byte/half patterns,
full expert shapes and raw FP32 chains. Full-size startup passes. Linked BMG
assembly reduces static instructions from 2955 to 2566, but adds 1,664 bytes
of spills and 52 scratch messages. It fails the no-spill gate and is excluded
from all microbenchmarks and sealed screen views. No device verdict exists.

Evidence: `evidence/cpu-byte-identity.json`, `evidence/full-shape.json`,
`register-report-offline.json` and its compressed assembly/vISA. The failure
shows that replacing cheap immediate-bank selection with many dependent SLM
reads increases live state; a lower instruction count is insufficient.

Revisit only with a distinct bounded-liveness mechanism and new no-spill proof.
No geometry sweep, device retry or approximate scale was used.
