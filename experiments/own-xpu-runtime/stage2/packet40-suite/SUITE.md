# Packet 40 sealed suite protocol

`window.py` is the device entry point. Its exact commands and prerequisite
order are in WINDOW.md. `suite.py` and `pipeline.py` default to the CPU backend;
this packet's preparation did not execute any device binary.

Use `--max-new 64` with the complete twelve-prompt 64-token oracle manifest,
or `--max-new 128` with the complete 128-token manifest. The input bundles are
cap-independent. A smaller positive `--max-new N` is also accepted when the
manifest oracle covers N; every emitted token is checked against that prefix.
Retention ranges are sorted, deduplicated and clipped to the requested cap
before the wrapper records or compares them. A subset manifest is accepted and explicitly marked partial;
a subset cannot establish the complete suite result. Every requested prompt
must fit `prompt_tokens + max_new <= context_capacity`. Current windows use
capacity 256. Requests end naturally on EOS; they are never padded or retried.

Each attempt begins with one excluded five-token synthetic warmup request that
is absent from every contiguous suite-prompt span. It requests two outputs,
including both target and draft heads. Warmup alone suppresses EOS so both
outputs execute. A complete state reset follows, and then each manifest prompt
runs exactly once. Every request starts from empty prompt/KV/history state;
`cached_tokens=0` records that explicit reset contract. Optional repeats are
separate attempts and have separate summaries. The primary summary uses attempt
one; a separately named pooled compatibility value matches the historical
reference table's treatment of observed repeated rows.

`--retain-steps none` is required for speed windows. The 64-token exactness
companion uses `1-8`; the 128-token companion uses `1-8,97-104`. Retention is
instrumentation: snapshots are taken from target streams into a separate
buffer, and that buffer is cleared after readback. It cannot select arithmetic,
change token authority, or enable cache reuse. The final full-state CPU gate
checks both ranks, both state banks, draft state and standalone mutable scratch.
The speed wrapper names a passed exactness companion of the same boot, binary
seal, card pair, dispatch, controller, prompt overlap, cap and prompt set.

Admission freezes the manifest and input-bundle bytes, verifies one common
model/plan identity, and runs the exact read-only oracle checker on the oracle
itself. Each request then compares every emitted token to the hash-bound oracle
result without tolerance. Exactness windows additionally compare every selected
layer fixture byte. A token or fixture mismatch marks that request failed and
the remaining prompts still run. A rank/process or storage failure follows the
cooperative stop path rather than launching another server.

Every request retains timestamps in seconds from the monotonic clock, TTFT,
prompt/output token counts, requested cap, output/prompt token hashes, natural
stop/early-end flags, wall throughput, draft guesses/hits/misses and hit/miss
cycle times. The raw timestamp count must equal the emitted-token count, and
all timestamps must be finite and strictly increasing, including those after
the measured window. The enclosing wrapper binds the binary, dispatch,
environment, boot, card pair and exactness companion.

The three deliberately separate timing fields are:

* `fixed64_tok_s`: `63 / (t64 - t1)`. It requires 64 generated events and counts
  natural EOS at event 64. This is the requested fixed 63-interval figure.
* `decode_tok_s`: the historical reference-table comparison,
  `(N - 1) / (tN - t1)`, where N is at most 64 and excludes the final EOS event.
  It is null for fewer than two non-EOS events. The original 28.49 tok/s table
  excluded immediate-EOS decode rows and reported per-repeat and pooled
  observed-row medians; this field preserves that explicit convention.
* `tok_s_1_100_intervals_after_ttft`: `99 / (t100 - t1)`. It requires 100
  generated events; natural EOS at event 100 counts. The numerator is 99,
  never 100. This is a rate over the whole timestamp span, not a median of
  per-interval reciprocal durations.

The submission-style primary statistic first takes the median within each
prompt class, then the median of those class medians. The class map matches
`scripts/qualify_realistic_window_metrics.py`: operations, code, prose, analysis,
documentation and structured-writing. The all-prompt median, mean and p10 are
also reported. Retention/class instrumentation and CPU runs expose diagnostic
window accounting but leave speed-eligible fields null. Failed/partial attempts
are explicitly labelled, and missing values never become invented results.

A 128-token run can supply the 100-event metric. It does not pass the public
fixed realistic final gate: that gate requests a 512-token cap and requires
complete quality/determinism/promotion evidence. `realistic_final_gate.passed`
and the payload gate marker therefore remain false in this packet. No external
submission is created by these wrappers.

`test_suite_metrics.py` checks hand-computed formulas, class aggregation, EOS,
all-event timestamp guards, incomplete suites, retention/cap guards, failures
followed by successful requests, and all twelve token oracles at both caps.
`suite_gates.py` retains the inherited state-reset, order, controller and
manifest-binding checks. `full_wrapper_gate.py` runs every window wrapper
through its CPU backend success and ordinary failure paths; CPU receipts cannot
authorize a device prerequisite. K0's JIT body and device timing remain explicit
coordinator-only gates.

The inherited `suite_export.py` and `retain_window.py` utilities retain their
frozen 64-token CPU qualification and original fixture-retention scope. They
do not export 128-token or retention-disabled windows. The packet40 window
wrappers write their own current receipts and compressed evidence, and
`full_wrapper_gate.py` archives its rehearsal evidence separately.
