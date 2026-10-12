# Packet40 suite runtime

Packet40 copies amended packet38 and separates exactness instrumentation from
speed windows. Work here is CPU preparation. No device ran and no packet40
model speed is claimed. Qualification status and binary identities are in
[build-receipt.json](build-receipt.json); an incomplete receipt is not admission.
The [parent copy inventory](parent-copy.json) distinguishes inherited historical
receipts from current packet40 qualification.

The target remains the **quantized compressed Unsloth UD-IQ3_XXS release**, with
arithmetic `iq3-p17-detmath-v2` and full BF16 KV/state. Rank1's unchanged target
head alone chooses emitted tokens. Every emitted token is checked against the
sealed oracle. The official draft head still uses its existing draft-only
8-bit expert requantization; neither target weights nor target arithmetic change.

The measured motivation comes from predecessors, not this packet. Packet36
produced 30.37 and 31.02 tok/s on the development prompt, with 53 of 63 guesses
right. A hit cycle took 28.7 ms and a miss 55.3 ms; draft wall time was 4.3 ms,
of which 3.3 ms was GPU work. Packet37's halves took 20.7 + 20.7 ms; its all-right
21.3 ms/token diagnostic is not real draft performance. The twelve-prompt
reference is 28.49 tok/s. See [packet36 receipts](../packet36-draft/receipts-cards01-20261012-chain/README.md),
[packet37 receipts](../packet37-merged2/receipts-cards23-20261012-chain/README.md),
and the [schedule analysis](../schedule-model-20261012/README.md).

The coordinator's newer packet38 suite completed 24/24 requests exactly, with
1,536 tokens and 9,216 fixtures: retained-instrumentation medians 38.27 and
38.25 tok/s by repeat (38.25 pooled), versus sequential 25.36 pooled. The
[predecessor evidence note](PREDECESSOR-CARDS.md) records its metric/population
caveats and K2 watchdog/storage lessons. These are not packet40 measurements.

Previous windows copied 48 layer snapshots for each of the first eight output
steps. Those instrumented steps took 30–68 ms instead of about 27 ms; recorded
mean token time was 32.9 ms versus a 27.8 ms median. Removing those copies is a
measurement correction, not a claimed kernel gain. `--retain-steps none` is for
speed; `1-8` and `1-8,97-104` are exactness diagnostics. The speed receipt names
a completed exactness window on the same boot with the same inputs and identity.
CPU gates compare tokens and final mutable state for retention on and off.
The strict terminal-EOS case remains unresolved: timing-dependent abandoned
speculation can leave different unused physical bytes, although committed state
and tokens agree. [EOS-STATE-SCOPE.md](EOS-STATE-SCOPE.md) records the exact
limit. An owner decision or a new full-state rollback proof is required before
sealing; no exception has been assumed.

`--max-new N` is bounded by prompt length plus context capacity. With capacity
256, the suite's 60–90-token prompts fit 128 outputs. The complete 64- and
128-token manifests are accepted, as are explicit subsets; subset summaries
say partial. Each suite warms a distinct synthetic request, fully resets, and
uses each selected prompt once per attempt. Failed exactness requests do not
prevent the remaining requests from running. Repeats are reported separately.

The suite records token timestamps, prompt/output counts and hashes, TTFT, wall
rate, early ends, guesses, hits and hit/miss cycle times. It reports the fixed
64-event comparison and the 100-event submission metric, plus the separately
labelled historical reference-table EOS accounting and class aggregation.
[Window commands](WINDOW.md) and [deadlines](DEADLINES.md) define the prepared
sequence. A 128-token cap can measure the 99-interval rate but cannot pass the
full 512-cap publication gate; no submission is made here.

The historical 28.49 reference uses llama.cpp commit
`23b0202a189c44a54625aadcb37a946dd1d6278d`, F32 arithmetic, FP16 KV and
context 4096. Its median has eleven finite prompt rates because code-review
ends immediately. The new arithmetic-v2 oracles produce all 64/128 tokens for
all twelve prompts. A common rate formula therefore does not establish matched
arithmetic, outputs or prompt populations. Keep this historical comparison
separate from matched packet40 controls; see
[the independent metric review](review-metrics-second-independent.md).

The draft uses K2 choices for matching classes and weight formats. Native rank1
submits the draft then its confirmed half without a host wait for the guess.
Private pinned read-back and a separate completion sequence publish the guess
as soon as its event completes. Python remains a synchronous reference path.
Draft provider failure yields no guess; an actual owner/device failure remains
a failed window. See the independent ordering and token-authority reviews.

A known miss now stops rank0 before its next actual compute submission. It
drains all submitted work, restores the pre-half state selection and history,
and redoes from the target token. CPU gates visit every miniature compute launch
boundary and seeded random real-model boundaries. [ROLLBACK.md](ROLLBACK.md)
describes the state and event lifetime rules. Cancellation cannot retract kernels
already queued. If the whole half is submitted before a miss arrives, it saves
no compute; issued-launch and cancellation counts make that measurable. CPU
correctness does not establish a device speedup.

The amended missing-RssAnon default is retained. The seal includes both
`nongemv_fixture_host_sha256` and `cpu_tests_sha256`. Every wrapper is rehearsed
end to end on CPU, including its summary and failure handling; rehearsal
receipts cannot authorize device work. K0's driver image build and K2's GPU
timings remain device-only qualifications. Wrapper format/storage errors do not
write the boot fault latch.

Current evidence is summarized in [CPU-RESULTS.md](CPU-RESULTS.md), with the
[inherited-gate checklist](qualification-checklist.md) and
[binary hashes](BINARY-HASHES.md). [CLOSEOUT.md](CLOSEOUT.md) records the scope,
findings and outstanding work. [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md) preserves
failed approaches; [INTEGRATE.md](INTEGRATE.md) gives the next-packet handoff.
