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
on 2,333 temporary synthetic records. Seven artifact-tampering checks refuse
changed inputs. This establishes accounting behavior, not a measured hit rate.
Early natural EOS is retained and marks the requested 24 × 256 scope incomplete.

The final contract test includes a cancelled five-layer speculative prefix.
The converter checks native completion/cancellation timings; interrupted
speculation is retained without pretending it was a complete model pass.
Replay assumes every observed cache admission completes, even after a cancelled
route. Since fills change later hits, this is a declared policy scenario, not
a universal upper bound or proof that all selected experts executed. A pure
CPU-miss design can use the frozen static cache directly. Adaptive LRU/LFU
also needs the GPU weight-fill cost; CPU computation cannot populate that slot.

## Route preparation and final review complete

The [separate route variant](../experiments/own-xpu-runtime/stage2/packet55-feasibility/route/README.md)
builds for native device use and CPU use. It logs ordered target and draft
IDs/weights to fixed 124-byte records after router timing. It preserves the
production arithmetic and increases only this diagnostic's response cap to
256. The 24 prompts are independent of the benchmark suite; admitted GGUF
header reads total about 21.9 MB, with no tensor payload read.

The CPU controller comparison passes two requests per fresh engine, including
reset and MTP: tokens, guesses, **206 target-state hashes and 10 draft buffers**
match the uninstrumented baseline. The diagnostic records 28 route observations,
including four draft observations. Four wrapper/schema tests also pass.
Native source closure binds 133 project dependencies and the host closure 126.
The inherited CPU validation-header path caused a compile refusal; the isolated
host header copy fixed it. Its failure and correction are retained.

[Independent review](../experiments/own-xpu-runtime/stage2/packet55-feasibility/REVIEW-INDEPENDENT.md)
closed the cache-admission, early-EOS scope and cancelled-prefix findings.
[Final checks](../experiments/own-xpu-runtime/stage2/packet55-feasibility/preparation-check.json)
verify current source/binary/test bindings and count **71,545,339 bytes** across
the packet, comfortably below the 1 GB build limit. No GPU executable, service,
throughput run or model tensor payload was used during preparation. Packet49d,
sealed sources, the existing oracle and the memory fence remain untouched.

The coordinator's commands and estimates are in the component runbooks:
[route, 30–90 minutes](../experiments/own-xpu-runtime/stage2/packet55-feasibility/route/README.md),
[quiet CPU, 10–20 minutes](../experiments/own-xpu-runtime/stage2/packet55-feasibility/cpu/README.md),
[H2D, two fresh 1–3-minute windows](../experiments/own-xpu-runtime/stage2/packet55-feasibility/h2d/README.md),
and [offline analysis, 2–10 minutes](../experiments/own-xpu-runtime/stage2/packet55-feasibility/analysis/README.md).
The route command requires cards 2+3 and 97 GiB available host memory; free
cards alone do not admit overlap with packet49d. The MTP source exception
remains unanswered as of this preparation. The runner refuses without it.

Build the exact one-layer streaming control first, then use measured misses,
CPU latency and transfer latency to choose a full design. The feasibility
document also keeps host staging/repacking explicit: original CPU GGUF rows
and GPU compact rows have equal byte counts but different serialized layouts.
No adaptive GPU fill, second host bank or same-card draft time is free.

## Coordinator decisions (2026-10-17 11:27 UTC)

- **MTP draft source:** `--allow-existing-p49c-draft` is authorized.
  - The IQ3-only weight restriction came from my brief, not from an owner rule.
  - The draft is the same official one-token MTP head that the 2-card record engine (packet 45 SPEED6 and packet 49c) has used under the owner's weight-source policy. No new weights are introduced.
- **No overlap with packet 49d's chain.** The H2D probe drives the copy engine on cards 2/3:
  - card 2 = PCI `0000:43:00.0`, which has the GuC hard-lockup history;
  - card 3 = `0000:47:00.0`, which had today's 01:09 BCS engine reset.
  A fault there would stop 49d's queue through its journal check, and a third fault this boot halts device work.
- **Order after 49d completes:**
  1. quiet CPU benchmark, with GPUs idle;
  2. H2D-a, then H2D-b, on card 2;
  3. route window on cards 2+3 (needs 97 GiB available host memory);
  4. offline locality analysis.

## Memory-fence finding and packet 55 wrapper alignment (2026-10-17 13:25 UTC)

H2D-a refused before any device work: "memory fence 53–57 changed". The live state on boot `2cba7160`:

| Block | State |
|---|---|
| 53 | offline |
| 54 | offline (failing region) |
| 55 | offline |
| 56 | offline (failing region) |
| **57** | **online** |

`b70-offline-bad-memory.service` reported success at boot. Its contract, in the unit comment, is that blocks 54 and 56 hold the regions that fail the memory test, while 53, 55 and 57 are margin, and "a block that cannot be offlined (unmovable kernel pages) is left as it is".

- **Re-offline attempt:** the coordinator retried with sudo under the owner's 2026-10-03 standing authorization to re-apply the fence. The kernel refused with "unmovable page". That page was cached content of the IQ3 GGUF on the FUSE (ntfs-3g) mount; FUSE pages cannot migrate. Nothing changed.
- **Cache drop:** not attempted. A cache drop would free the pages, but the owner forbids cache drops.
- **Exposure:** block 57 was almost certainly online all boot, so every device result today, including the three records, ran in this state. The failing blocks were offline throughout.
- **Wrapper change:** `h2d/window.py` `memory_fence` (also used by the route window) now refuses unless 54 and 56 are offline, and records all five states in every receipt. The unit test covers the margin-online and failing-online cases.
- **Evidence:** the refused `h2d/evidence/h2d-a` is retained. The rerun uses new output names.
- **Owner note:** to get block 57 offline, offline it at boot before the USB model disk is mounted and read.

## Device results (2026-10-17 13:18-13:44 UTC, boot 2cba7160, no new fault lines)

Compact receipts: `experiments/own-xpu-runtime/stage2/packet55-feasibility/evidence-copy/`.

**Exact CPU experts (quiet window, GPUs idle).** Byte identity with the GPU order passed. The best rate is **5.6-6.5 GB/s at 12 threads**, about 350 µs per expert amortized. Per-layer latency is 1.4 / 2.1 / 3.5 ms for 4 / 6 / 10 misses. One thread does 0.48 GB/s; 16 threads drop to 4.7 GB/s, plausibly because of SMT siblings. **The CPU-exact miss path is about 10x too slow.** It is set aside as not viable on this host.

**H2D on card 2 (two fresh windows, after one refusal on the fence check).** Bandwidth is 24.6 GB/s for 4 experts (7.9 MB) and **27.7 GB/s for 10 (19.7 MB)**, about 72 µs per 1.97 MB expert. The copy engine overlapped synthetic compute almost completely: concurrent ≈ copy + 10 µs.

**Route locality (cards 2+3).**
- **Run:** the sanity prompt matched the oracle. 24 independent calibration prompts × 256 tokens were all generated and the scope is complete; 12 train and 12 held-out test prompts. The draft is the existing p49c MTP head.
- **Two analysis fixes:**
  - `route/convert.py` and `analysis/locality.py` read `generated_tokens` from each request's result.json. It is null there; the count lives in `output_tokens` and in the window summary. Both now take the window summary's count and require it to equal `output_tokens` and the token-list length.
  - A partial output from the failed first conversion is kept as `routes.jsonl.gz.failed-partial-20261017`.

Decode-phase byte hit rate on the held-out prompts:

| Cache | LRU | LFU | static per-layer |
|---|---:|---:|---:|
| 8 GB | 0.766 | 0.582 | 0.445 |
| 12 GB | 0.850 | 0.690 | 0.577 |
| **18 GB** | **0.925** (0.75 missed experts, 1.49 MB per layer visit) | 0.809 | 0.722 |
| 24 GB | 0.958 | 0.891 | 0.825 |

Recency dominates: routes are strongly temporally local.

**Decision: the one-card design is a GPU expert cache, 18 GB LRU, with exact H2D streaming of misses on the copy engine.**
- About 1.5 MB per layer at 27 GB/s is about 55 µs per layer, mostly hideable behind post-router work.
- Planning projection: about 34 ms GPU plus 1-3 ms exposed streaming per token, so **about 27 tok/s** without batched MTP verification. The llama.cpp one-card reference is 15.9-21.6 tok/s.
- Every expert, hit or miss, runs on the GPU with today's kernels, so the packet 49 oracle stays valid.
- Next: packet 58 builds this engine.
