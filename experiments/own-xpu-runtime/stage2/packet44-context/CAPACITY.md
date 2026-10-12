# Capacity inventory (2026-10-12)

Arithmetic identity: iq3-p17-detmath-v2. The copied baseline and hashes are in
baseline.json. Allocation capacity C is distinct from valid positions n.

| Component | Baseline entry | Storage | Per-token work / packet44 treatment |
| --- | --- | --- | --- |
| Target QSA keys/values, twelve layers | packet3/step/plan.hpp, main.cpp initialize | 2048 C bytes/layer, BF16 | append one row; attention only selected positions |
| Raw/pooled index | plan.hpp, kernels.hpp pool | 256 C + 256 ceil(C/4) bytes/layer | replace ceil(C/4) launches by newly completed pool plus append |
| Index score/select | round2.hpp, specialised.hpp | C/4 float scores; 2051 int IDs | score valid complete pools, stable rank by descending score and lower block ID; bound launches by 32-position buckets |
| Attention scores/probabilities/masks | kernels.hpp, round2.hpp, specialised.hpp, p30_attention.* | fixed 24*2051 floats each; -1 selection suffix | launch selected upper bound, true selected n controls every tree; unused score tails are scratch |
| Draft cache | mtp.hpp | same BF16 cache formula, one layer | separate draft position and independently refreshed prepared sites |
| RoPE | rope.hpp, rope.bf16, build.py | extend 4096 to 32768*128 bytes | one row lookup; preserve old bytes exactly |
| Counters/bounds | main.cpp, native_controller.hpp, rank.hpp | fixed int counters | raise limits; request positions and speculative redo remain checked |
| Prepared arguments | adapter.cpp, runtime_kernels.hpp, main.cpp, mtp.hpp | bounded structs <=1024 bytes | add launch extent, recapture only select/attention when bucket changes; track both banks |
| Rollback | rank.hpp, request_reset.hpp | recurrent alternate bank, no duplicate KV | append-only invalid rows overwritten by redo; revalidate bucket on each half |
| Fixtures/K2/admission | fixture_driver.cpp, window.py, memory_gate.py | context-specific fixtures; per-rank plan | finite 6/7 timing shapes, watchdog admission; BF16 memory floor 1.5 GB |

Capacity-derived offsets and guards must remain capacity-derived. Replacing them
with n changes addressing. Reductions must keep their actual valid leaf count,
including odd-tail +0 operations. Short requests use the same launch buckets at
all capacities. Pool launch count is independent of C. Bucket rebuilding is
outside the kernel but inside request wall time and must be measured later.

Packet42 measured 0.5–1.5 microseconds per additional launch and a several-
microsecond penalty for poorly used groups/local barriers. Therefore merely
launching C groups and early-returning is rejected. Existing dispatch names and
arithmetic stay intact; scheduling bounds change. Device timing remains pending.

Fixture serialization is also capacity-sensitive: historical fixture headers
contain eight integers even though the in-memory Shape now has nine fields.
Both readers preserve the old header width and initialize extent separately.
The adapter fixture sizes RoPE from rope_constants::bytes, not its old literal.
