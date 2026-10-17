# Packet 55: one-card IQ3 feasibility preparation

The owner requested three measurements before choosing a one-card engine:
route locality, a new exact CPU expert implementation and expert-slab transfer
latency. Preparation is CPU-only on `steve-b70s`, nice 19, affinity
`4-15,20-31`. The coordinator owns every GPU window and quiet CPU throughput
window. Packet49d-round3, the existing oracle, sealed packets, services and
the memory fence at blocks 53–57 remain untouched.

`git pull --rebase` completed on main before work; no incoming change was
needed. Root free space was about 18 GB. Packet55 has a 1 GB total build cap,
serial compilation, compact route logs and bounded transfer buffers. No model
payload, GPU, sudo, service, power, swap or page-cache operation was performed
while writing the initial plan.

The [feasibility equations](../experiments/own-xpu-runtime/ONE-CARD-FEASIBILITY.md)
charge actual executed routes and same-card MTP work. Missing timings are
explicitly pending. The three measurements select a design; actual one-card
GPU layer timing, CPU mailbox and CPU/DMA contention still need integration
measurements before an end-to-end speed claim.

The initial dependency check found that packet49c loads its existing MTP
weights from `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`, while the owner's
packet55 weight-path allowance names only the three target GGUF shards under
the admitted IQ3 directory. A narrow question asks whether the coordinator may
reuse those existing hash-bound draft weights. Preparation does not read them.
Until resolved, a draft route window must refuse rather than silently widening
the admitted source paths.

Credit Niko1221 / Strata for the cache/CPU-miss idea, as already recorded in
ONE-CARD-DESIGN. The implementation is independent lab code and reuses only
the lab's arithmetic definitions, fixtures and safety mechanisms.

Detailed component checks, commands and retained evidence will be appended
as preparation completes. No route hit rate, CPU throughput, H2D bandwidth or
one-card speed has been measured in this preparation.

## Transfer component prepared

The [H2D probe](../experiments/own-xpu-runtime/stage2/packet55-feasibility/h2d/README.md)
compiles to a 159,280-byte binary. Three CPU-only guard/summary tests pass.
It selects an actual copy-only Level Zero queue, checks physical card 2 or 3,
and covers ordinary and exceptional expert sizes at 4–10 slabs per batch.
Peak pinned host allocation is 23,300,096 bytes. No native program was run.

The coordinator's two fresh windows will record standalone and concurrent
copy/compute durations, route-known-to-resident wall latency and full transfer
byte verification. Overlap is reported from duration envelopes inside a host
wall span, without subtracting unrelated clock epochs. The synthetic source
is already pinned; pageable-to-pinned staging remains a separate engine cost.

## CPU expert byte gate passed

The independently written row-vector AVX2 kernel passes both fresh CPU fixture
processes: **54,001 checks each**, 18 complete experts, 80,640 BF16 values and
60 raw NaN/Inf arithmetic cases. Gate/up, deterministic SiLU product and down
match the packet49c production CPU arithmetic. The existing packet46 fixture
digest also matches, `0ea0eeaa89bce627`. IQ3_S layer 2 is checked and benchmarked
separately. [Build receipt](../experiments/own-xpu-runtime/stage2/packet55-feasibility/cpu/evidence/build-corrected/receipt.json),
[two fresh byte checks](../experiments/own-xpu-runtime/stage2/packet55-feasibility/cpu/evidence/test-corrected/receipt.json).

The first test harness incorrectly reduced the same mutable reference tree
twice; its failure is retained. The fix stores the first reference result.
No candidate arithmetic tolerance or output change was introduced.

The [quiet CPU command](../experiments/own-xpu-runtime/stage2/packet55-feasibility/cpu/README.md)
runs two fresh processes at each of 1, 4, 8, 12 and 16 threads, measuring both
formats and actual 4/6/10-miss layer batches. The allowed affinity contains 12
physical cores, so 16 threads means 12 physical cores plus four SMT siblings.
Expected peak resident memory is 256 MiB, with zero pinned host memory. It must
run only while all GPU windows remain stopped. No throughput run occurred.
Actual device output and exception/status integration remain separate gates.

## Offline cache accounting passed its CPU checks

The [analyzer](../experiments/own-xpu-runtime/stage2/packet55-feasibility/analysis/README.md)
uses fixed per-layer quotas for LRU, LFU and static placement at 8/12/18/24
decimal GB. It reproduces packet46's 18 GB allocation exactly, separates
payload from padded slots, trains on twelve independent prompts, and resets
that trained state for each of twelve held-out prompts. Initial fills,
prefill and decode are separate; every repeated speculative visit is charged.
The full draft stays resident outside the target cache. Twenty-four GB is a
sensitivity point, not an admitted one-card setup.

Independent review caught a false-miss case when one selected expert evicted
another from the same route. The corrected policy snapshots all ten hits and
protects those slots before filling misses. Nine CPU tests now pass, including
real binary conversion, provenance validation and all twelve cache settings
on 2,328 temporary synthetic records. Six artifact-tampering checks refuse
changed inputs. This establishes accounting behavior, not a measured hit rate.
Early natural EOS is retained and marks the requested 24 × 256 scope incomplete.
