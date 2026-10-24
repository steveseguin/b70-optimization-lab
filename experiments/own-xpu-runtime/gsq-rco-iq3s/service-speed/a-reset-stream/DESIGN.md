# SC117 RESET evidence option and confirmed-token stream

Source-only candidate, 2026-10-24. No native build, model inference, device access,
service operation or deployment was performed. Seven copied sources and their
patches pass byte/hash checks; 16 synthetic parser tests pass. Device equality and
latency remain unmeasured. See `source-check.json:2-3`, `python-tests.txt:18-21` and
the exact scope in `verify_packet.py:1-9,82-88`.

## Source identity and citation key

All line numbers below are **physical file lines**, not the historical `#line`
diagnostic locations. Paths are relative to `/home/steve/llm-optimizations`.
`L = experiments/own-xpu-runtime/gsq-rco-iq3s` and
`S = L/recurrent-f32/build/source-v2`. Expand aliases literally:

| Alias | Executed source, relative to repository root |
|---|---|
| E | `S/experiments/own-xpu-runtime/gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp` |
| ENTRY | Same directory as E, `entry.cpp` |
| R | `S/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp` |
| P | `S/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine` |
| N | `S/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src` |
| V | `S/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native` |
| PY | `experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/pipeline.py` |
| LAN | `L/serving/lan` |
| J | `L/recurrent-f32/evidence/native-build.json` |

`C(path)` means this packet's `source/<full repository-relative executed path>`.
`source-manifest.json:2-50` lists all seven full paths, original SHA256s and copied
SHA256s. Every original hash matches J's source receipt (`source-check.json:4-46`).
The baseline binary is **5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4**
(J:1223). ENTRY:2 includes E; E:1841 includes R; R:267-269 include the RESET,
native and V3 controllers. Only entry.o depends on these changes; all 40 existing
object dependency files were checked (`source-check.json:48-297`; BUILD.md).

This patch preserves the corrected engine's existing arithmetic; it does not fix
or certify its broader fidelity. The corrected engine diverged from the independent
CPU reference at output71 on the incident prompt (`L/recurrent-f32/operating/longer-a/RESULT.md:3-16`).
No tolerance is accepted here: equality to the unchanged corrected engine must be
exact in both emitted IDs and full target state. No weight, KV, activation,
verifier, recurrent precision or arithmetic change is proposed (patches/01-07;
`prepare_sources.py:24-98`).

## A1: omit evidence, preserve reset

Measured service RESET calls were 4.18 s and 4.10 s (`LAN/RESULT.md:19,23`).
Those measure the **whole A.reset call**, not disk writes alone (`LAN/service.py:280-282`).
Target raw state is 310,364,224 bytes; draft raw state is 9,699,332 bytes, totaling
**320,063,556 bytes** (`LAN/README.md:87-88`). The selftest released 320,459,412 bytes
including surrounding artifacts (`LAN/RESULT.md:6`). Removing dumps targets those
readbacks, hashes and writes; the time saved cannot be claimed until measured.
Zeroing and other reset work remain (`P/request_reset.hpp:20-49`).

Implemented CLI options are independent, process-wide and default-preserving:

| Option | Default | Effect |
|---|---|---|
| `--reset-dump all\|none` | `all` | Guard only state_dump, request_state_inventory and provider dump at RESET |
| `--finish-dump all\|none` | `all` | Guard only provider dump at FINISH |
| `--token-stream none\|jsonl` | `none` | Enable A2 on rank0 |

Definitions and strict value validation: `C(E):148-150,187-194`.
RESET guard: `C(P/request_reset.hpp):14-15`. FINISH guard: `C(R):381`.
Both rank launch commands must carry the requested dump policy. No current
launcher is edited; the existing transport constructs argv at `PY:298-324`.
`--reset-dump none` deliberately does not disable explicit DUMP commands,
per-step diagnostics or FINISH evidence (`R:365,381`; `P/native_controller.hpp:100`).

### State and ordering proof from source

The dump functions are read-only with respect to model arithmetic state:

* `state_dump` reads target plan buffers and alternate banks, hashes them, writes
  bundles and serializes history/FP32-cache metadata; no target mutation or bank
  swap appears (`R:250-257`).
* `request_state_inventory` drains and reads/hashes the remaining mutable
  allocations and host metadata; no target mutation or swap appears
  (`P/request_state_inventory.hpp:6-28`).
* `DraftRuntime::dump_all_state` calls dump (five draft buffers), then reads/hashes
  mutable allocations and writes JSON. It has no separate commit, bank swap,
  provider poll or provider-specific synchronization (`N/mtp.hpp:301-308`).

They are **not side-effect-free in the literal runtime sense**. Readback drains,
overwrites pinned host staging, waits/retires events and increments transfer
telemetry (`E:987-1000`; `V/engine_bracket.hpp:193-198`). Retirement updates
`retirement_calls` and `retirement_ms` (`E:749-754`); the kernel-I/O path increments
`kio_sync_transfers` (`V/engine_bracket.hpp:198`). `Engine::wait` can invoke the
draft progress callback (`E:948-957`). Those effects must not be confused with
target model state, and their counters need not remain equal.

For a normally completed service request, draft work is already resolved: the
controller consumes draft publication in the next iteration, starts none on the
terminal iteration and requires `!draft_pending` before returning
(`P/native_controller.hpp:73-76,92-102`). `poll_result` clears `async_pending` and
`progress_pending` before publication (`N/mtp.hpp:274-281`; `R:324-327`). This
argument does not grant permission to RESET a malformed in-flight request.

All synchronizing/mutating boundary work remains in precisely its original order:

1. `image.boundary()` and V3 reset still run before request_reset (`R:366`). The
   boundary completes deferred restore, rejects unresolved speculation, drains,
   scrubs dirty snapshot storage and clears snapshot host bookkeeping
   (`N/strict_snapshot.hpp:463-482`). This is NOT optional dump work.
2. The initial target drain and sticky error read remain (`P/request_reset.hpp:9-10`).
3. Class reporting and bank normalization remain (`P/request_reset.hpp:16-17`).
   The bank swap drains, swaps buffers/prepared-command banks, flips parity and
   invalidates FP32 cached-source metadata (`E:1161-1167`).
4. Every allocation zero, history/control restoration, metadata/cache clear,
   drain, counter reset, output stream reopen, provider reset and receipt remains
   byte-for-byte unchanged (`P/request_reset.hpp:20-49`; `C(P/request_reset.hpp):20-49`).
   Provider reset rejects pending work and clears its own mutable state, position,
   disabled flag, publications, staging and callbacks (`N/mtp.hpp:291-298`).

FINISH can omit the same read-only provider evidence: approximately 9.7 MB
(`LAN/README.md:103`). It keeps rank1 report flush, unresolved-candidate/V3 checks,
snapshot boundary processing and the original teardown (`R:381,418-422`). Owner
shutdown still waits and refuses an unsafe exit (`E:1726-1734`). No synchronization
is replaced by sleep or inferred from elapsed time. FINISH remains separately
enabled by default so research users retain their end-state artifact.

Missing dump directories do not intrinsically break current retention: it checks
existence before removal (`LAN/service.py:253-266`). Live storage forecasts and
the live service are unchanged. A future integration must explicitly record
which evidence it disabled, and must not expect RESET/FINISH artifacts when their
options are `none` (CLI and guards above).

## A2: a lossless log of confirmed emitted IDs

An individual target token is already briefly visible in shared memory, but
there is no reliable per-emission stream available to Python:

| Existing channel | What it exposes and when | Source |
|---|---|---|
| Verification slot | One target token and release sequence; overwritten each position, published before controller accept/rollback. A poller can miss positions; a double sequence read does not make the token/sequence pair atomic. | `R:97-105,209`; `P/native_controller.hpp:87-99` |
| Draft publication | Speculative draft ID and provider timings, never safe as user output. | `R:323-328`; `P/native_controller.hpp:77-79` |
| Native mailbox | One overwritten command/reply pair, no retained emission list. | `P/native_controller.hpp:12-19,37,50` |
| progress.jsonl | Flushed upload or checked-site progress, no confirmed emitted IDs. | `E:1121-1125,1720-1722` |
| timings.jsonl | Per-half timing/position/speculation, no emitted ID; newline writes, flushed after native request. | `R:229-241,400` |
| p150 | Thread-local timing samples, no output IDs, flushed after native request. | `V/split_timing.hpp:3-15`; `R:400` |
| reply_report | Deferred work; its flush does not flush the ostream. Host rows lack emitted IDs. | `P/reply_first.hpp:22-26,48-58` |
| native-result.json | Complete tokens and target completion stamps, serialized only after run returns. Python first waits for both ranks. | `P/native_controller.hpp:89,104-112`; `R:397-400`; `PY:143-151` |

Implemented: rank0 exclusively creates **`<current rank0 output>/confirmed-tokens.jsonl`**
before entering either controller. Permissions are 0600; `O_EXCL|O_NOFOLLOW`
reject stale files and symlinks. This is a new regular file, not a pipe. A2 changes
no shared-map layout, mailbox, kernel, target data or original completion stamp.
(`C(P/native_controller.hpp):65-101`; `C(R):397-405`.)

Wire format, in order:

```json
{"type":"begin","schema":"sc117.confirmed-tokens.v1","request_sequence":7,"limit":512,"vocab":248320}
{"type":"token","index":1,"token_id":42,"target_completed_monotonic":123.456}
{"type":"end","count":1}
```

`request_sequence` is rank0's outer NATIVE command sequence, not a draft/mailbox
sequence (`R:380,383,392`; `C(R):399`; `PY:381-384`). Indices start at one and
are contiguous. EOS is included exactly when it is in the final native token
list. No extra text/token is synthesized (`C(P/native_controller.hpp):126-139`).
Native `write(2)` writes each complete line immediately, looping only for EINTR
or short writes. There is no stdio buffering or fsync. Readers consume only
newline-terminated records and keep partial tails (`C(P/native_controller.hpp):67-99`;
`stream_parser.py:76-98`). End seals the token list, **not overall request success**:
the coordinator still requires both valid replies and exact final-result
reconciliation (`C(R):403-411`; `stream_parser.py:100-125`).

Publication points, all after existing target confirmation and resolution:

| Case | Standard controller | V3 controller |
|---|---|---|
| EOS | After optional pending rank0 rollback | Same |
| Output cap | Before terminal break; `more=false` means no next speculation | Same |
| Ordinary emitted token | After hit ACCEPT or miss rollback + corrected half + ACCEPT | After those actions and V3 boundary |

Exact hooks: `C(P/native_controller.hpp):127,129,137-140` and
`C(V/v3_controller.hpp):37,39,45-48`. They publish only `out.tokens.back()` and
its existing timestamp. The prefill fixture guard suppresses prompt tokens.
The original target timestamp stays where it was; notification on a miss is
later because correction completes first (`P/native_controller.hpp:87-100`).
Both controllers are covered because R:397 chooses at runtime. The current LAN
rank0 draft setup is the standard path; V3 requires rank1 draft
(`LAN/README.md:47`; `V/v3_controller.hpp:11`).

With streaming off, there is no stream open/write, just an empty callback check.
With it on, the normal case adds one small host write per emitted ID, plus begin
and end records: **514 writes for 512 outputs** absent EINTR/short writes. No
device readback is added (`C(P/native_controller.hpp):67-101,127-140`; `C(R):397-405`).
This can perturb timing and overlap; it is not claimed to be zero overhead.
The JSONL is a latency feature, not a throughput optimization.

### Python integration boundary and parser

The protected service, adapter, observer, tokenizer and pipeline are not edited.
This packet supplies a standalone strict parser, not a live SSE deployment.
The existing service calls NativeController synchronously (`LAN/service.py:287-303`)
and its SSE path waits then emits the answer (`LAN/service.py:423-458`).
Future integration can use the existing transport check callback: io invokes
check_alive and polls at up to50 ms intervals (`PY:328,344-348`).

Proposed coordinator steps, in a separately reviewed adapter:

1. After any RESET, choose `(t.request_output / 'rank0' / 'confirmed-tokens.jsonl')`
   or the initial `t.out / 'rank0'` path. Capture `expected_sequence=t.seq[0]+1`
   **before** NativeController starts. Verify the path does not exist. Instantiate
   `ConfirmedTokens(expected_sequence,count,vocab)` (native path: `C(R):399`;
   sequence source: `PY:381-384`; RESET destinations: `LAN/adapter.py:196-206`).
2. Compose `t.check` with its existing health callback; do not replace health,
   timeout or stop logic. After the original callback, tail at most64 KiB from a
   regular-file descriptor, retry absent file only before begin, and call
   parser.feed on newly read bytes. Track the descriptor/inode and offset; reject
   truncation/replacement. Put returned token records on a bounded in-memory
   queue for the HTTP thread. Never block the native reader on a slow client.
   This is a proposed integration, not implemented service code (`PY:328,344-348`;
   parser API: `stream_parser.py:31-98`).
3. After both waits succeed, drain the file to EOF and call parser.finish(result).
   Require exact IDs, count, indices and completion stamps. End alone, a partial
   stream or an old native-result file never certifies success. Restore the
   original check callback in a finally block. No resume/retry/gap filling is
   proposed (`PY:148-151,368-370`; `stream_parser.py:100-125`).
4. Text/SSE integration must use the pinned tokenizer incrementally with UTF-8
   boundary buffering, EOS filtering, stop-string tail withholding and thinking
   tag handling; token-by-token decode-and-concatenate is not a proven equivalent
   to full decode. Reconcile final rendered text exactly before claiming SSE
   equivalence. This is deliberately future integration work: current service
   documents post-generation stop strings and reasoning handling
   (`LAN/README.md:52-58`). Do not change those semantics silently.

The stream uses one exclusive file per current output directory, so a second
streamed native run without RESET fails rather than truncates. LAN already uses
a fresh directory between requests (`LAN/service.py:278-287`). Rank0 is the only
writer; rank1 produces no stream. On write/close failure the exception follows
the existing peer abort and safe teardown path (`C(R):408-428`). Already delivered
confirmed tokens cannot be retracted; the HTTP request must end as failed, never
with a fabricated successful terminal. Stream content is request text evidence
in token form and needs the same bounded retention as its request directory.
The candidate does not introduce a background writer, retry loop or server restart
(`C(P/native_controller.hpp):67-101`; `C(R):397-428`).

## Verification plan — separate device authorization required

Nothing below was run during Task A. The current host restrictions remain in
force. Use a later isolated authorized test window and output directories; do
not exercise or restart the live LAN service to test this packet.

Pinned CPU-only input preparation is in `verification-inputs.json`. It contains:

* LAN selftest: the existing87 input IDs and expected32 output IDs from
  `LAN/selftest.json:4-129`, cap32.
* **Exactly512 input tokens**, historical-reading512, cap512, copied from
  `L/coverage/manifest.json` (preparation identity at
  `L/coverage/prepare_prompts.py:16-18,30`). This is raw continuation, not chat.
* The same87-token incident prompt at cap512, matching the longer corrected-engine
  investigation (`L/recurrent-f32/operating/longer-a/RESULT.md:3-7`).

Keep natural EOS. Historical coverage output/state came from an older engine and
is **not** an oracle for this candidate. Generate new complete5926 state evidence
for all three cases. The pinned input JSON records both source hashes and each
compact-JSON token-array hash (`verification-inputs.json:1-5` and its case fields).

Required matrix (every cell is planned, no pass inferred from source review):

| Build/configuration | Purpose |
|---|---|
| Unchanged5926 binary, existing flags | Authoritative corrected-engine control |
| Original entry.o relinked with required precision link flags | Isolate the documented link-flag difference |
| Candidate defaults (`all/all/none`) | Prove disabled features preserve behavior |
| Candidate reset none, finish all, stream none | A1 RESET isolation |
| Candidate reset all, finish none, stream none | A1 FINISH isolation |
| Candidate reset all, finish all, stream jsonl | A2 isolation |
| Candidate reset none, finish none, stream jsonl | Combined service candidate |

For each, use the same exact weights, official draft, split24/24, context4096,
runtime selection, full BF16 KV/F32 recurrence, template/input IDs, EOS list and
greedy target verifier as control (`LAN/README.md:109-124`; `ENTRY:4`). Test both
target-only and MTP. Retain at least two fresh processes per configuration, and
within each process repeat the next-request sequence after RESET. No warmed
prompt/cache reuse, precision reduction or permissive tolerance is admissible.

1. **Exact emitted IDs and complete target state.** Capture explicit DUMP at
   position2147483647 before RESET on both ranks; this remains available with
   reset-dump none (`R:365`). Compare every target bundle entry and complete
   mutable-allocation inventory byte-for-byte/SHA256, with matching names,
   shapes, scalar types, lengths, logical positions, history and bank/cache
   metadata (`R:250-257`; `P/request_state_inventory.hpp:6-28`). Include BF16 KV
   unused tails, F32 recurrent/history, alternate banks, token history, snapshots
   and scratch; do not accept sampled hashes. Match logical buffer identities,
   not host addresses or allocation IDs across processes. Missing fields/bytes
   fail closed. Ignore only non-model timing/file-path/host-address metadata under
   an explicit schema list, never unexplained target bytes. Explicit readback is
   for correctness arms; it is excluded from later dump-free latency arms.
2. **RESET equivalence and next-request equality.** Run selftest→RESET→selftest,
   512-input case→RESET→selftest, and selftest→RESET→512-input case. Keep reset-dump
   all in control and none in candidate. Capture immediately after RESET and after
   the following request. Require identical full target reset state, identical
   next-request tokens, full target-state hashes, MTP accepted/rejected counts
   and final logical state. Check both fresh-process repeats and both input
   orders. Dump presence is the only intended evidence difference; reset.json
   allocation count/zeroed-byte count must match (`P/request_reset.hpp:20-49`).
3. **Streaming safety.** Require exactly one event per final ID, no prompt or
   guessed IDs, identical original completion stamps, correct EOS/cap terminal,
   and exact stream/result reconciliation. Exercise count1, early EOS, cap32 and
   cap512; confirm real MTP hit and miss coverage (selftest has26 accepted and5
   rejected proposals: `LAN/RESULT.md:6-7`). Test non-overlap/target-only, and use
   bounded synthetic controller fixtures for forced misses and V3 branch coverage
   in a future authorized build. Test fragmented reads, stale file/sequence,
   disk write failure and incomplete end in isolated output directories; require
   failed request plus original cooperative shutdown, never process killing.
4. **FINISH.** Compare target state immediately before FINISH and next fresh-process
   outputs with finish-dump all/none. Require unchanged safe ownership drain and
   successful terminal receipts; only draft-final-state evidence disappears.
   There is no next request in a finished process (`R:381,418-429`).
5. **Timing only after exactness.** Separately measure RESET wall time (readback,
   zeroing and total), bytes written, prompt time, target completion timestamps,
   first stream arrival and end-to-end delivery latency. Compare stream off/on
   with matched cold requests across at least two fresh owners, report all runs
   and drift. File-write/JSON/poll overhead and delayed publication after a miss
   must be included. Keep explicit state-capture work outside the timed window.
   No speed gain is claimed by this source packet.

Build instructions retain all compile flags and add precision flags at link as
required; that discrepancy from the old receipt is itself an equality gate
([BUILD.md](BUILD.md), J:5-18,507-556). Any token or target-state mismatch blocks
adoption; diagnose it without changing the oracle or accepting a tolerance.

## Local validation and remaining risks

`python3 -B verify_packet.py` checks original hashes against the build receipt,
applies each unified diff in memory and compares exact copied bytes, verifies
all changed absolute includes bind to copies, and scans all40 dependency files
to establish entry.o-only rebuild. It also runs the16 parser tests
(`verify_packet.py:17-88`; `source-check.json`; `python-tests.txt`). No compiler
syntax/device proof is implied. Source readers independently reviewed RESET and
stream hooks; the durable proof remains the source and test artifacts.

Remaining risks are unmeasured device determinism under changed host timing;
the precision-link difference; fewer evidence-readback failures caught before
RESET; synchronous regular-file write latency/disk exhaustion; one-stream-per-
directory restriction; and future incremental text/SSE semantics. Their controls
are the exact-state matrix, preserved sticky/boundary checks, exclusive framing,
strict parser and separate integration work above. This packet is ready for
review, not deployment or a quality/performance headline.
