# One-card cache budget refinement

October 17, 2026. Metadata-only design. No allocation, payload read, device
query, or fit test. [Generator](cache_budget.py) and [exact table](cache-budget.json)
refine [ONE-CARD-DESIGN](../../ONE-CARD-DESIGN.md); all quoted bandwidth
requirements below are scenarios, not observations.

Use the current expanded target nonexpert layouts and the complete resident
draft, sharing the target head and one RoPE table. Keep full BF16 KV at 4K.
The target weights remain the independently qualified mixed-format Unsloth
UD-IQ3_XXS quantized compressed version.

The earlier table's PLE history formula was short by 122,880 bytes: the retained
packet45 census allocates **184,320 bytes**, not 61,440. It also has 16 bytes of
token history. Target recurrent state is therefore **59,019,280 bytes**, and
target KV/index plus recurrent state is **175,411,216 bytes**. The new checkpoint
allowance uses that complete recurrent total. This still does not prove that
one recurrent checkpoint covers the speculative write set: scratch, controls,
KV suffixes and private draft rollback need their own byte inventory before
integration. The 1 GiB transaction allowance is provisional, not that proof.

The 18 GB cache now includes 4 KiB-aligned complete-expert slots, a 64-byte
metadata allowance per slot, a direct `(layer, expert)` slot map and a layer
directory. Ordinary expert payloads are 1,971,200 bytes; layer-2 experts are
2,329,600 bytes. The aligned strides are 1,974,272 and 2,330,624 bytes.
The unchanged packed formats are stored directly; no expanded CPU/GPU copy
or lower-precision representation is hidden in this cache.

| Cache component | Bytes |
| --- | ---: |
| Packed expert payload | 17,970,176,000 |
| Aligned expert slots | 17,997,688,832 |
| Lookup/slot/layer metadata | 684,032 |
| Total cache allocation | **17,998,372,864** |
| Unused within the 18 GB cap | 1,627,136 |

This holds **9,082 complete experts**, versus the prior payload-only 9,097.
The initial policy is independent of prompt content: IDs 0–188 in every
layer, with ID 189 also in the first ten ordinary layers (0, 1, 3–10).
The generator records every ID and offset stride. This is a reproducible
control placement, not a claim that low IDs are hot. Calibration may propose
a better placement only from separate, valid IQ3 route traces.

The combined design total is **29,818,616,662 bytes**. It leaves 2,393,638,058
bytes below the 30 GiB arena. Against a conservative 32 decimal GB card and
the unchanged 1.5 GB physical reserve, only **681,383,338 bytes** remain.
Keep both tests: the arena is an allocation ceiling, and the physical reserve
also covers memory outside that arena. Actual driver/code pools, prefill peaks,
graph overlap and complete rollback can consume this remaining margin.

The bounded pinned mailbox allowance is 5,898,240 bytes: two generations for
48 layers, each with one BF16 input, ten complete BF16 outputs and 4 KiB of
route/status tags, rounded to 4 KiB. This is host memory, separate from the
256 MiB device transfer allowance. Implementations should reuse slots across
layers once completion proves safety. Never reuse them by elapsed time alone.
All packed expert, PLE and embedding backing totals **77,949,322,240 bytes**;
draft backing, OS/driver memory, loader copies and CPU workspaces are additional.
The approved memory fence and all host settings stay unchanged.

Under hypothetical uniform routing, this placement has a **36.9546% byte hit
rate**, **302.617 missing experts** and **598.780 MB of CPU expert bytes** per
target position. At 60 target positions/s, the CPU would need **35.9268 GB/s**
of exact packed expert processing and **18,157.0 experts/s**. Actual emitted
token requirements additionally depend on rejected target work. CPU benchmark
results must be compared to this as a scenario, not as a measured hit rate.
Per-layer miss tails and the dependent layer boundaries remain the deciding
test; aggregate GB/s alone does not qualify a one-card engine.

Credit Niko1221 / Strata for the publicly described GPU hot-expert cache and
CPU miss arrangement already recorded in ONE-CARD-DESIGN. This refinement and
its code are independently authored from the lab census; no Strata code was
read, copied or ported.
