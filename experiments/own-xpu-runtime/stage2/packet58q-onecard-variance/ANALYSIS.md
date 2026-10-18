# Packet58q: production slowed in host preparation; tile16 is not immune

CPU-only analysis, October 18, 2026. **Production's 24.969 → 20.999 tok/s
drop is almost entirely added host preparation associated with major page
faults.** The same token steps grow by 7.4085 ms; preparation grows by
7.3364 ms (99.0%). Expert misses and bytes are identical. The leading cause
is nonresident file-backed embedding/PLE lookup pages, **not file-backed
expert misses**: both production and tile16 copy their expert banks into
pinned host allocations. Tile16 happened to have zero major faults in 58n;
the source does not give its lookup pages different backing or guarantee that
state in 58p. The earlier tile16-containing port itself suffered major faults.

## Comparable evidence and numbers

The copied [analyzer](analyze.py) joins all five arms at each of **2,386
positions**: 850 prefill and 1,536 decode. The tables below use **1,188
generated positions, indices 2–100**, matching the 99 intervals from generated
timestamp 1 to 100 in each of twelve prompts. Rates are recomputed from those
timestamps. Mean token-wall spans and medians of request rates are different
statistics; do not invert one to claim the other.

Inputs: [58k screen](../packet58k-onecard-screen/evidence/card0-screen-b/)
and [58n screen](../packet58n-onecard-loo/evidence/card0-loo-a/). All five have
the same boot, native binary hashes, environment, card 0, CPU placement,
plain target-only decode, BF16 KV, 4096 context, 18 GB immutable expert cache,
zero-copy miss path, prompt order/hashes and exact output hashes. Production
has the same selection hash in all three windows. The model is the Unsloth
UD-IQ3_XXS **quantized compressed version**, arithmetic
`iq3-p49-split32-v1`. Each screen uses 12 prompts once, 128 output tokens,
`cached_tokens=0`, and no prompt/KV/response reuse. These are screens, not the
strict 512-token final gate or fresh-process performance repeats. 58k's final
control was cancelled; its bracket is incomplete.

| Rate, tok/s | 58k production | 58k port | 58n before | 58n tile16 | 58n after |
| --- | ---: | ---: | ---: | ---: | ---: |
| All-prompt median (brief's statistic) | 24.969353 | 22.181405 | 20.999190 | 26.274164 | 21.335658 |
| Median of six class medians (registered primary) | 24.888137 | 21.927475 | 20.793904 | 26.162365 | 21.017146 |

| Mean per charged token | 58k production | 58k port | 58n before | 58n tile16 | 58n after |
| --- | ---: | ---: | ---: | ---: | ---: |
| Complete token step, ms | 39.9414 | 45.1393 | 47.3499 | 37.9703 | 47.0369 |
| Host preparation, ms | 0.5835 | 8.4143 | 7.9199 | 0.5117 | 7.7394 |
| Major faults | 0.1263 | 12.7020 | 11.7365 | **0** | 11.4394 |
| Minor faults | 16.8973 | 4.3013 | 5.2660 | 17.0185 | 5.5631 |
| Expert misses/fills | 33.0051 | 33.0051 | 33.0051 | 33.0051 | 33.0051 |
| Logical miss bytes, decimal MB | 65.456571 | 65.456571 | 65.456571 | 65.456571 | 65.456571 |
| Of which down weights, MB | 30.417455 | 30.417455 | 30.417455 | 30.417455 | 30.417455 |
| Host enqueue loop, ms | 7.5737 | 7.2980 | 8.1652 | 7.6588 | 8.0787 |
| Host waits, ms | 26.2238 | 24.3890 | 26.0863 | 24.3873 | 26.0379 |
| Cache planning/fill/publication, ms | 7.1072 | 6.9672 | 7.1857 | 7.0250 | 7.0341 |
| Selected transfer helper spans, ms | 0.4198 | 0.7637 | 0.8039 | 0.4660 | 0.8810 |
| Wall minus preparation, ms | 39.3579 | 36.7250 | 39.4300 | 37.4586 | 39.2975 |
| Zero-copy device time | not measured | not measured | not measured | not measured | not measured |
| GPU compute time | not measured | not measured | not measured | not measured | not measured |

**The timers overlap; do not sum these rows.** Preparation includes lookup
uploads/waits, cache time includes publication/waits, and GPU execution overlaps
CPU submission. Host wait is not GPU time; transfer helpers are not PCIe miss
read time. All receipts have `profiling=false`, `timing=token`, empty
`sites.jsonl`, zero device-time placeholders and null family timers. Those
zeros cannot support a GPU-time number. Actual PCIe transaction bytes and
DMA-only durations are also absent. The logical miss bytes are subsequently
copied into the device cache; they are not a measurement of total bus traffic.

Cache fills, fill bytes, evictions and resident bytes match **position by
position across all five arms**, not just on average. Expert hit rate is
93.123948%; logical byte hit rate is 93.108094%. All have 1,790 kernel
submissions per charged token except the full port's 1,646 (route fusion).

## Where production's extra seven milliseconds went

| Difference from 58k production, ms/token | 58n before | 58n after |
| --- | ---: | ---: |
| Total wall increase | +7.4085 | +7.0955 |
| Preparation increase | **+7.3364** | **+7.1559** |
| Remaining wall increase | +0.0721 | −0.0604 |

The preparation/major-fault correlations across charged positions are
**0.9786 before and 0.9767 after** (58k port: 0.9853). Every prompt shows the
effect: 58n-before preparation means span 6.693–9.112 ms, after
6.545–8.928 ms, versus 0.501–0.529 ms for tile16. Tile16 has zero major faults
on every charged position and in prefill; it still has about 17 minor faults
per token. Fault-free major counts do not mean no mappings are created.
Full per-prompt and phase statistics are in [analysis-data.json](analysis-data.json).

This makes production's **regression page-fault-sensitive**, with strong
evidence for lookup I/O. It does not make the entire runtime page-fault-bound:
roughly 39.4 ms/token remains outside preparation. There is no isolated
fault-service timer, fault-address trace, per-file residency capture or
per-process I/O trace, so neither exact disk-wait time nor the faulting file
can be proven from these counters alone. No corrected throughput is claimed.

The source distinction matters:

- [prepare_token / lookup / Weights::read](../packet58j-onecard-port/main.cpp)
  fetch the token embedding and sixteen history-derived PLE rows on the CPU,
  dequantize them and upload the results. The same exact tokens/history choose
  the same rows in every arm. [Slice](../packet2/loader/gguf.cpp) uses a
  read-only `MAP_PRIVATE` file mmap followed by unmap; copying a row first
  requires touching that source. All native receipts say
  `lookup_residency.enabled=false`. No one-card arm calls `warm_lookups`.
- `load_expert_bank` allocates `Memory::pinned` for **both** layouts and copies
  every expert bank there before decode. Tile16 additionally transposes down
  weights in bounded chunks into that same destination. GPU cache misses
  dereference this pinned bank, not the GGUF mmap. Neither layout gains an
  exclusive anonymous/pinned expert-copy advantage. Driver-managed pinned
  allocations should not be equated with `/proc` RssAnon accounting.
- Tile16 changes down addressing/grouping and launch geometry. It does not
  change PLE lookup storage, the cache policy, expert bytes or the lookup
  instruction path. Its longer/different loading work may affect residency
  indirectly; the receipts do not establish that causal link. The fault-heavy
  58k **port also has tile16**, disproving inherent immunity to lookup faults.

| Host/load observation | 58k production | 58k port | 58n before | 58n tile16 | 58n after |
| --- | ---: | ---: | ---: | ---: | ---: |
| Load-and-pin seconds (outside decode) | 41.227 | 140.361 | 114.729 | 78.549 | 120.006 |
| Minimum MemAvailable, decimal GB | 70.206 | 70.944 | 70.403 | 70.971 | 69.699 |
| Maximum accounted bytes, GB | 82.514 | 82.513 | 82.515 | 82.516 | 82.516 |
| Process VmSwap after load, KiB | 0 | 0 | 0 | 0 | 0 |

All native receipts report 52,637,635,560 model payload bytes read. Anonymous
peaks are about 359–360 MB in all five monitors; this does not include the
whole driver-managed pinned bank. The 58n global SwapFree deltas are −0.545,
+0.020 and +0.004 MB, respectively; those are not per-process swap counters.
Zero VmSwap after load and the source path favor file-backed lookup faults
over swap-in, without proving fault addresses. The supplied idle RAM figure
(~112 GiB available), root free-space change (20 → 40 GB), offline blocks
53–56, intervening two-card jobs and archive moves are context from the brief,
not a reconstructed event trace. File copies and model loads can disturb page
residency; merely freeing filesystem space or having available RAM does not
reload absent lookup pages. We cannot assign this change to the archive move,
root free space, offlining, or any particular intervening job.

## Tile16's real mechanism and the size of the confound

The saved K1 fixtures retain a host-read improvement even when full-model
production slows. These are **ten-expert IQ4 down fixture event times**, not
whole-model zero-copy time per token:

| Arm | All-host down K1a / K1b, ms | Aggregate useful host bandwidth K1a / K1b, GB/s |
| --- | ---: | ---: |
| 58k production | 0.910198 / 0.899766 | 13.964 / 14.026 |
| 58k port | 0.418125 / 0.417531 | 17.561 / 17.468 |
| 58n before | 0.902703 / 0.895505 | 14.002 / 14.030 |
| 58n tile16 | 0.418411 / 0.427948 | 17.580 / 17.357 |
| 58n after | 0.878370 / 0.900953 | 14.138 / 14.018 |

The [packet125 micro result](../../../../notes/2026-10-18-own-runtime-packet125-micro-result.md)
also reports 1.26/1.27× for tile16's simulated-miss fixture. These support
better host-read locality, not a 27% whole-model prediction. Do not divide
the model's 65.46 MB by fixture bandwidth and label the quotient measured
zero-copy time.

Against 58n-before, tile16 saves 9.3795 ms/token, **7.4082 ms (79.0%) in
preparation**. Against after, it saves 9.0666 ms, **7.2276 ms (79.7%) in
preparation**. The controls differ by only 1.60% in all-prompt rate, yet both
fault heavily and the candidate does not. A tight bracket does **not** bound
this candidate-specific residency difference. The observed +23.15% over the
better control is real for these windows, but cannot all be assigned to the
down kernel. Comparing the two low-fault windows across screens gives
24.969 → 26.274 tok/s (+5.23%) and 1.8993 ms less non-preparation wall; that is
an unmatched diagnostic comparison, **not a controlled tile16 speed claim**.

## Risk to 58p and permitted handling

**No, the chain cannot be assumed to see 58n tile16's host state. Yes, page
residency can swing this result by much more than a few percent.** The unchanged
production selection already moved −15.90% in all-prompt rate across screens,
almost wholly alongside lookup preparation/faults. The candidate retains
the same sparse file-backed lookup mechanism. Its one observed zero-fault
window does not establish future zero-fault behavior or a 26.27 tok/s floor.

The sealed [58p chain](../packet58p-onecard-record/README.md) runs
K1a → K1b → KD → W2m → WS → WS128x → WS128, with 90-second gaps. Model windows
use fresh native processes and reload weights. KD/W2m use one prompt with
eight tokens; WS/WS128x traverse the twelve-prompt suite before the only timing
window, WS128. Those necessary gates may leave file pages resident. Conversely,
each reload and unrelated host I/O can change that state. Fresh process and
`cached_tokens=0` do not establish a cold filesystem cache; nor does fresh
allocation ensure a warm one. WS128x is exactness-only, not a second timing
measurement. The earlier screen had two fixtures then one model load per arm,
so its history is not identical to this seven-window chain.

Keep the sealed order, gaps and full-host exclusion as registered; do not
reorder or add quality passes to warm a selected prompt set, and do not retry
a slow window. The coordinator can avoid scheduling optional bulk archive
work during its chain without killing anything or changing host settings.
After each window, read the already-produced preparation/fault, load-time,
host-memory and miss-path receipts. Report the actual WS128 rate together
with that state; keep all prompts/tokens and both good and slow windows. A
future matched comparison needs the same declared load/quality order in
both arms and fresh independent timing evidence, not post-hoc subtraction.

**Do not add an ordinary sequential model-file pre-read for this chain.**
[AGENTS.md](../../../../AGENTS.md) says “No swap toggles, cache drops or
host-controlled benchmark wrappers”; its cold-response rule allows resident
weights, initialized runtime and compiled kernels while forbidding prompt/KV/
response reuse. That does not forbid every ordinary file read, but it does
not authorize a separate page-cache-conditioning pass to improve a record.
The applicable [58n boundary](../packet58n-onecard-loo/DO-NOT-REPEAT.md) is
explicit: “Do not subtract lookup faults from speed, warm prompts/pages, drop
caches, discard slow tokens or retry for favorable host state.” A pre-read
whose purpose is warming pages falls within that boundary even without a
sysctl change. Natural residency from the existing necessary gates should be
disclosed; do not add or manipulate gates to manufacture it. No pre-read is
recommended or performed here.

**Coordinator recommendation:** Run 58p only through its existing admission
and quality gates, in its sealed order, with lane B kept out and optional bulk
file work deferred during the chain. Expect possible page-cache variation,
not a guaranteed 26.27 tok/s. Preserve and report WS128's actual preparation
time and major/minor faults alongside speed and load order; the 58n +23%
screen win is substantially confounded by lookup residency. Do not pre-read
the model, alter settings, rerun for a faster cache state, subtract fault time,
or use WS128x as an independent speed repeat. Keep the second fresh timing
repeat and strict 512-token gate explicitly pending before any broader record
claim; this CPU analysis changes neither the frozen chain nor its readiness.

## Reproduction and preservation

[analyze58n-original.py](analyze58n-original.py) is a byte-for-byte copy of
58n's tool; [tool-provenance.json](tool-provenance.json) pins it. Only the new
58q copy is adapted: five-arm alignment, explicit unavailable GPU/zero-copy
times, constant-fault correlation handling (undefined, stored as null),
identity checks and chain/status evidence. It makes no resource-limit change.
The original 58n analysis of 58k is reproduced exactly for rates, existing
timing summaries, cold start and host-memory summaries.

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet58q-onecard-variance/analyze.py < /dev/null
```

[analysis-inputs.json](analysis-inputs.json) binds input bytes to paths and
SHA-256 hashes and gzip snapshots; missing originals replay from the snapshots
inside 58q, never by restoring into frozen packets. [Position rows](position-pairs.jsonl.gz)
retain all five arms at every aligned position. These small evidence copies
contain no model payload. No GPU, service, sudo, setting change, cache drop,
large model-file read, process kill, queue edit or external submission occurred.
