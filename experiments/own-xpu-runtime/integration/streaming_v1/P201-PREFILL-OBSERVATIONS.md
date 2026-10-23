# Packet201 prompt-processing observations

## Question and identity

Where does the observed wait for first streamed text occur, and which next
serving optimization has the largest measured recurring budget? This is a
read-only analysis of the closed packet201 run: one unchanged packet198 owner,
BF16 state, context4096, 21,552,729,600-byte expert cache, 16 requests and 1,484
generated tokens. It is not a throughput record or a new performance experiment.

The [source-bound receipt](receipts/p201-prefill-observations.json) records all
16 rows, timing definitions, cache deltas and hashes of 68 inputs. The
[independent device audit](../../stage2/packet201-streaming-serving/evidence/independent-device-result.json)
already verifies outputs and state. Client frame-receipt observations are not
native latency measurements.

## Outcome

Prioritize a real prefill path for fresh longer prompts. The current engine
processes each prompt token through the single-token launch/drain path. For the
370-token fresh chat, native prefill consumes **10.790s of a 15.404s native
request** (70.0%). The 394-token edited prompt consumes 11.690s. A smaller decode
micro-optimization has much less opportunity in these requests.

| Request | Input / prompt tokens actually stepped | Native prefill | Restore | Client first text / finish |
| --- | --- | --- | --- | --- |
| First A | 87 / 87 | 28.129s | — | 28.829s / 38.671s |
| B | 60 / 60 | 1.900s | — | ordinary HTTP |
| A append | 370 / 28 | 0.867s | 0.400s | 2.582s / 8.808s |
| Same chat, fresh | 370 / 370 | 10.790s | — | 11.511s / 17.170s |
| Edited A | 394 / 394 | 11.690s | — | ordinary HTTP |
| Final A | 87 / 87 | 2.922s | — | ordinary HTTP |
| Final B | 60 / 60 | 1.916s | — | 2.600s / 8.432s |

These native and client intervals have different boundaries. In particular,
client finish includes the normal postreply disposition. Their difference is
not a separately measured transport or checkpoint overhead.

## What worked

Append reuse removes known work: the restored state has 342 processed tokens
and one pending token; the 370-token prompt adds 27 tokens. The engine steps
the pending token plus that delta, exactly 28 tokens. Restore plus append
prefill takes 1.267s, versus 10.790s for fresh prefill, a 9.523s observed phase
difference. This is intentional serving reuse, with exact generated-token
agreement, not an eligible cold benchmark gain. Fixed request order and expert
cache history are not controlled away.

The ordinary fresh370 row has 369 non-final prompt steps, plus the last prompt
step producing the first output token. Those 369 steps issue 409,590 kernels
and 2,214 host waits: **1,110 submissions and six waits per token**. Their
summed wall time is 10.749s; summed enqueue-loop time is 1.796s and host wait
time 7.208s. Median prompt-step wall time is 28.36ms. This supports targeting
prompt computation and its repeated synchronization, not HTTP formatting.

For scale only, halving the measured fresh370 prefill phase would save 5.395s;
eliminating it entirely has a ceiling of 10.790s for that request. Reducing the
measured post-first-token decode wall sum by 3% would save about 0.120s. These
are sensitivity calculations, not predicted or measured candidate gains.

## What failed or remains uncertain

The first A is a distinct first-use event. Its very first prompt step takes
23.594s (83.9% of prefill), with 23.511s reported inside enqueue, 663 process
major faults and 57,755 minor faults. Only 0.094ms is in resident-lookup
preparation. The first position records **zero scheduled expert-cache fill
bytes**; positions 2/3 show the delayed route-driven fill pipeline beginning.
Thus the 23.594s cannot honestly be called cache-copy time. Lazy runtime/kernel
initialization, paging and first-use host expert access are hypotheses requiring
a separate phase attribution. Prepared commands were captured before READY;
capture alone does not prove all first-execution costs were paid.

The expert cache does begin empty, and first-prompt fills are explicitly charged
inside requests. By the first A prompt's end, cumulative scheduled fills reach
13.54GB; by its request end they reach 22.79GB. Across all 16 requests they reach
120.99GB. These are cumulative scheduled bytes, not residency or hit rate, and
not additive stall time. The first/final A difference includes different cache
and runtime histories; it is not a measured optimization speedup.

Device event timings are disabled: zero gemv/non-gemv device fields and null
family breakdown mean unavailable measurements. Host wait time can overlap
queued computation and transfer; it is not an independently removable 7.208s.
The result field `first_generated_token_ms` is the single last-prompt step
(28.680ms for fresh370), **not time to first output**. Prefill already includes
that step, so adding it again double-counts.

## Evidence and patches

No runtime patch, native execution, service action or settings change was made.
Only this note and its receipt are added outside the sealed packet201 input map.

Relevant hooks in packet198's local generated `build/native/main.cpp`, pinned by
the [source-overlay receipt](../../stage2/packet198-postreply-checkpoint/evidence/source-overlay.json)
and rehashed in this analysis:

- Lines2220–2237: fresh and append prompt loops invoke `step` serially;
  checkpoint restoration precedes append processing.
- Lines2116–2177: each `step` prepares the token, enqueues the launch plan,
  drains compute/readback, and collects routes for cache maintenance.
- Lines1587–1616: prepared prompt commands skip final/logits/argmax work but
  retain the single-token execution plan.
- Lines670–700 and1073–1088: asynchronous cache fills, publication and prior
  route collection; counters advance on fill submission, not proven completion.
- Lines1022–1046 and2002–2025: empty cache creation, load/prepare and READY
  boundary. Recorded load-and-pin time is 215.788s, separate from request prefill.
- Lines2194–2207: token wall/enqueue/wait accounting and the first-step timer.

## When to revisit

The next substantive candidate should make fresh prompt processing efficient:
bounded multi-token/chunk prefill with prompt-specific matrix work and fewer
token-boundary round trips. Preserve exact arithmetic, BF16 state, causal
attention and recurrent-state ordering; the hybrid model makes this more than
replacing a loop with independent parallel tokens. First isolate which repeated
waits are required for state/cache correctness, then prove intermediate state
and output parity before a controlled device comparison. Reuse is already a
separate serving feature and must not substitute for the fresh-prompt test.

Keep first-use attribution as a second, separate question. A phase trace around
first enqueue/runtime initialization and host expert accesses could distinguish
the 23.594s stall; these receipts alone cannot. Any future comparison must keep
initial cache policy, owner lifetime and prompt identity explicit, with first
request and later fresh requests reported separately.
