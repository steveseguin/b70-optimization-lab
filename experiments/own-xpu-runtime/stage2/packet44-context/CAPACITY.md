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

Compile-time shape constants also occur in `p33r2.cpp::issue` and
`p33_candidates.hpp::qsa_group`: capacity 128/256, budget 2048 and one token.
Those existing P33 attention candidates keep their fixed-capacity variants;
larger capacities take the same wrapper's existing generic round2 body, with
the admitted extent and valid reduction count. K2 must measure that candidate
at each new capacity. The copied production dispatch selects
`p30.attention.sg32`, whose body already takes runtime capacity/stride; its
implementation choice is unchanged. The P33 GEMV choices have no context
capacity parameter and remain unchanged. Budget 2048 always means 512 complete
four-position pools plus at most three tail positions, hence 2051 ID slots.

The host fixture oracle in `prototype/snapshot/reference.hpp` also separates
capacity from valid length. Its temporary arena and copied cache prefixes use
valid n; short cases keep the 64 MiB arena at every capacity, with a 768 MiB
upper bound for the largest synthetic cases. Fixture storage still includes
full-capacity allocation tails so the gates can detect unintended writes.
That storage and full evidence serialization are fixture costs, outside the
production token path.

Resume evidence scope: the GNU suite/pipeline receipts qualify valid bytes at
all three capacities. The separate Intel four-token composite qualifies the
requested reduced real-model path at 4,096; no complete Intel target matrix is
claimed. Both compilers already passed beyond-budget synthetic fixtures and
rollback checks. The seal binds the existing native guard admitting 128 output
tokens and context 32,768 to the actual compiled binaries. KD host references
are prepared only at the two requested coordinator window capacities.
