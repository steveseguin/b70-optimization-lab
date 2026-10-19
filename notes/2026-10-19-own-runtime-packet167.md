# Packet167 — two-card resident lookup applicability closeout

<!-- campaign-closeout -->

## Question and identity

**Close at the applicability gate; no resident candidate built.** Bundle 8 reads
both lookup tables from file-backed host mappings. However, all four packet136
suite windows, including the record WS128, have **zero recorded major faults**.
Both second fresh packet163/165 runs also have zero. This meets the brief's
near-zero record-window stop rule. The first fresh packet163/165 runs do have
faults; they are retained below, not relabeled as zero or removed from results.

The target is Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, the separately labeled
quantized compressed version, with `iq3-p49-split32-v1`, BF16 KV, bundle 8,
24/24 target placement and the unchanged target-verified rank-1 draft.
The existing record is **58.798109 tok/s**, packet136 chain a,
`cmve4dtir007wrf01k57sdf23`. Its scope is 128 output tokens; strict512 is false.
The submission template's older 23/25 wording is stale; the
[submission ledger](../results/localmaxxing-submissions.md#L1278) records that
correction. No speed or quality result is created by this audit.

## Outcome

The mechanism is technically portable, but the record's measured paging problem
is absent. Apply the requested early stop rather than commission a new device
test. Host-RAM admission, partial variants, compilation, bracket packaging,
lane proposals and READY are **not reached**. In particular, this closeout makes
no claim that another 29.3 GB fits, and counts no offline memory blocks.

### Source answer: mapped host rows, not whole tables on the device

All paths below are bundle-8 sources or their included loader/plan dependencies.
Their hashes are retained in the [audit](../experiments/own-xpu-runtime/stage2/packet167-twocard-resident/evidence/fault-audit.json).

| Boundary | What the source does |
| --- | --- |
| [plan.hpp:227](../experiments/own-xpu-runtime/stage2/packet3/step/plan.hpp#L227), [267](../experiments/own-xpu-runtime/stage2/packet3/step/plan.hpp#L267) | Declares the `per_layer_token_embd.weight` and `token_embd.weight` lookup operations. |
| [main.cpp:273–288](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/main.cpp#L273) | `lookup_mappings` stores `iq3::Slice` objects. `warm_lookups()` maps every embedding/PLE byte, applies the existing `MADV_WILLNEED`, touches every page and retains the mappings. This is page-cache warming at load, not an anonymous full-table copy or a pinning guarantee. |
| [gguf.cpp:133–139](../experiments/own-xpu-runtime/stage2/packet2/loader/gguf.cpp#L133) | A Slice is `mmap(PROT_READ, MAP_PRIVATE, file_fd, offset)`: file-backed host memory. |
| [rank.hpp:262–264](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/rank.hpp#L262) | Only rank 0 calls `warm_lookups()`. Its actual WS128 receipt records 29,321,610,240 bytes and zero load-touch major faults. Rank 1's receipt has `enabled=false`; its inherited reason string is not a topology diagnosis. |
| [rank.hpp:134](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/rank.hpp#L134), [main.cpp:1111–1156](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/main.cpp#L1111) | Rank 0 prepares each token's embedding and PLE IDs, reads the required rows, dequantizes them and uploads the resulting BF16 values. Its saved plan has `embedding` and `blk.1.ple.lookup`; rank 1's target plan has no lookup operation. |
| [main.cpp:376–389](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/main.cpp#L376) | Each bounded row read copies from a retained mapping when present, otherwise from a temporary model Slice. The temporary row vector is anonymous memory; it does not make the entire table anonymous-resident. |
| [main.cpp:891–896](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/main.cpp#L891) | The normal whole-weight device loader explicitly rejects embedding/PLE tables: only bounded lookup rows are allowed. |
| [mtp.hpp:229–230](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/mtp.hpp#L229) | Rank 1's draft separately reads the confirmed token's embedding through `e.w.read`, dequantizes and uploads that row. With no rank-1 retained lookup mapping, this uses the temporary file-backed Slice path. It does not read PLE. |

No existing page-cache advice was executed or changed by this CPU audit.

### Major faults in saved windows

These are sums of native `process_major_faults` differences, separately for
each rank, across the complete saved streams. They are **not whole-process
lifetime totals**. [rank.hpp:125–204](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/rank.hpp#L125)
places the counter around a target half, including rank-0 token preparation.
Load touching is separate; reset, draft and other activity outside the sampled
halves is not proved fault-free. Counts are not attributed to a file address.

| Window | Rank 0 / rank 1 timing rows | Major faults, rank 0 / rank 1 | Separate rank-0 load-touch faults |
| --- | ---: | ---: | ---: |
| packet136 W2m | 161 / 150 | 1 / 0 | 0 |
| packet136 WS | 2,717 / 2,386 | 0 / 0 | 0 |
| packet136 WSs | 2,386 / 2,386 | 0 / 0 | 0 |
| packet136 WS128x | 2,717 / 2,386 | 0 / 0 | 0 |
| packet136 WS128 (record) | 2,717 / 2,386 | **0 / 0** | 0 |
| packet163 full512 B-a | 9,347 / 7,856 | 590 / 0 | 4 |
| packet163 full512 B-b | 9,347 / 7,856 | **0 / 0** | 0 |
| packet165 warm512 B-a | 9,347 / 7,856 | 1,352 / 410 | 4 |
| packet165 warm512 B-b | 9,347 / 7,856 | **0 / 0** | 1 |

The packet136 suite rows cover all twelve requests once. Their distinct native
warm-up streams also have zero major faults and are counted separately in the
JSON. The packet163/165 rows include all thirteen requests, including prefill
and the first request. No prompt was selected, repeated or discarded here.
K0/K1a/K1b/K2/KD/W0p lack equivalent counters in this audit and remain unmeasured.

Packet163 B-a's 590 faults are all in rank 0's first `prefill512` operation:
0.236 ms preparation and 28,889.3 ms enqueue time. Packet165 B-a's first
`incident-retrospective` operation records 1,340 rank-0 and 402 rank-1 faults,
with preparation times 0.288/0.086 ms and enqueue times 28,981.1/21,243.6 ms.
Another **12/8 faults occur later in that same request**; all later requests
record zero. One later rank-1 row takes 349.242 ms to enqueue. These observations
are consistent with cold initialization costs, but do not prove the faulting
addresses or prove that all later faults are unrelated to lookup tables.
Both `-b` runs are separate fresh processes, not repeated prompts within `-a`.

## What worked

Tracing the reader distinguishes the retained file mapping from the small
anonymous row copy and from the device buffer. Replaying every recorded native
half exposes the cold-run exceptions that a single summary or load receipt
would miss. The audit checks required streams, integer nonnegative counters,
and exact stream counts; missing data cannot silently become zero. All
requested prior packet DO-NOT-REPEAT entries were read and their hashes saved.
Independent validation reread **210 unique streams / 89,255 native timing rows**,
recomputed the totals and hashes, and checked local links and the reserved JSON
hash-map keys. All checks passed; no missing or duplicate stream was accepted.

## What failed or remains uncertain

There was no candidate or failed device experiment. The one-card
[packet58aj gain](2026-10-19-own-runtime-packet58aj-result.md) cannot be assigned
to the two-card line. Zero major faults do not prove zero minor-fault cost,
future eviction immunity, or zero possible speed gain. The newer first-run
faults remain real; this is a scoped decision under the brief's record-window
rule, not a claim that every two-card run is paging-free.

## Evidence and patches

- [Read-only replay script](../experiments/own-xpu-runtime/stage2/packet167-twocard-resident/audit.py)
  and [compact evidence](../experiments/own-xpu-runtime/stage2/packet167-twocard-resident/evidence/fault-audit.json):
  every input timing-stream path/hash/count, all nonzero original timing rows,
  original load-touch receipts and source/exclusion hashes. No runtime patch.
- Original record streams remain under
  `stage2/packet136-record-bundle/build/device-cards01-a/{W2m,WS,WSs,WS128x,WS128}`;
  newer streams remain under each packet's `two-card/evidence/device-*/run`.
  These local raw streams are not tracked; the retained JSON is their compact
  audit, not a replacement full raw archive. Replaying requires those originals.
- [Negative-result index](../experiments/own-xpu-runtime/stage2/packet167-twocard-resident/DO-NOT-REPEAT.md).

Reproduce on CPU from the repo root, with stdin closed:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet167-twocard-resident/audit.py </dev/null
```

The audit was also run under a 3,906,250 KiB address-space ceiling (4 GB).
Only small source/receipt reads were used. No GGUF, full-shape model read,
native launch, GPU, service, sudo, setting or queue operation ran. Existing
packet trees and `ops/` stayed unchanged. The mixed `CURRENT.md` edits are
other work; this task changes no loaded model, host ownership or live state.

## When to revisit

Reopen with matched bundle-8 evidence showing a recurring lookup-related
steady-state major-fault problem, or a separately justified non-paging
mechanism. Keep the cold-run exceptions visible. Before any candidate build,
prove the real MemAvailable/GPUActive budget with at least 12 GB headroom,
excluding offline blocks 53–57, then implement and qualify the unchanged
arithmetic. Never infer the one-card gain, use prompt-specific resident rows,
or call this closeout a device speed test.
