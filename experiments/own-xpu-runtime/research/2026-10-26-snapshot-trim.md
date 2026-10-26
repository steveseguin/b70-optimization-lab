# SC117 two-card service: speculative snapshot trim (2026-10-26)

**Result: 47.97 → 48.32 tok/s, faster on 12/12 prompts, exact.** Engine `092da687b5d7` serves on cards 23/47.

## Where the two-card time goes (51ebe7496793 traces, last suite request)

- **Hit cycle.** Card 2's row (layers 23–47 and the head) is the bottleneck: about 17.2 ms of GPU work back to back,
  with no idle gaps. Card 1's path is draft 1.63 + pre-layer setup about 1.1 + layers 13.95 ms.
- **Card 1 slack.** Card 1 waits for card 2: median 0.44 ms, p10 0.16 ms. So moving a layer either way (about
  0.62 ms) loses. Split 23/25 stays.
- **Misses.** A miss leaves card 2 idle while card 1 runs rollback + redo, about 14.8 ms. Misses are 24% of positions
  and about 20% of decode wall time.
- **Head.** The target head is Q6_K at 1.38 ms per token, about 70% of bandwidth peak. Little to gain there.

## The change

The `SpeculativeImage` catch-all copied every live non-weight allocation on every speculative row and restored it on
every miss. That was 66 MB per capture, and it included the 36 MB batched-prefill shadows:
- `prefill_allocate` runs before the image is built;
- the shadows are not in `buffers[0]`.

Only `prefill_chunk` reaches the shadows. Its row views switch on at entry and off on every exit, and no speculation is
outstanding at that point. A decode half never touches the shadows, so the copy and the restore moved identical bytes.
The draft is constructed after the image, so its buffers were never included.

The patch excludes `card0:prefill:*` from the catch-all
(`engine/src/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/strict_snapshot.hpp`).

## Gates (all on device)

- **Startup:** F32 oracle differences `rank0: [] rank1: []`; prefill gate 13/13; continuation gate passed.
- **Suite:**
  - 5,965/5,965 output ids and 12/12 text hashes identical to 51ebe7496793;
  - MTP hits identical per prompt (4533/5954);
  - `cached_tokens` 0 on every request.

## Speed (same suite, same unit environment)

| | 51ebe7496793 | 092da687b5d7 |
|---|---:|---:|
| Suite median decode | 47.97 | **48.32** (+0.72%) |
| Snapshot per guess (rank 0) | 0.573 ms | 0.287 ms |
| Rollback per miss | 0.539 ms | 0.281 ms |
| Rank 0 layer body | 13.98 ms | 13.96 ms |
| Rank 1 half | 17.23 ms | 17.17 ms |

- **Unit environment:** split 23; draft prefix 91392; `banks-batch` + `static`; dispatch `gdn2`; merge checks; packet59
  draft kernels.
- **Engines:**
  - `092da687b5d7` is a rebuild of current `engine/src` (`59a4edd9243f`, built but not run on device) plus this patch;
  - the rebuild also compiles Codex's opt-in four-card sources;
  - the unchanged layer and half times, and the halved snapshot and rollback, attribute the gain to the trim.
- **Result:** files are `gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/f32-suite-092da687b5d7-prefill-snapshot-trim.json`
  and `serving/lan/evidence/*092da687b5d73fb7*`.

## Closed or not worth a cycle

- **Draft prefix 122,880.** It adds 29 hits per suite for 0.28 ms more draft time on card 1, about +0.2%. It is
  slack-limited; retest only if card 1 gains slack.
- **24/24 split.** Card 1 would become the bottleneck, and the redo would get longer.
- **Head on a third card.** Bound by the draft chain at about 17.1 ms per token: −1.8% at most.

## Next levers

1. Kernel work on card 2's layers. Rank 1's layers are not covered by the device profiler, because its mid-half
   reverse-export drain retires their events.
2. Card 1's remaining pre-layer host setup, about 0.4 ms before the snapshot.
3. The rest of the snapshot catch-all: `gemv-workspace` 8.4 MB copied in full. Excluding it would need the full-state
   gate to treat it as a scratch buffer.
