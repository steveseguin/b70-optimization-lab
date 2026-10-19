# Packet163: measure prompt reading and complete answers

CPU preparation only. No model, GPU, service or live queue was started or changed.
The two packets preserve the current 128-token record identities: packet136
bundle8 (58.798109 tok/s, two cards) and packet58aj (31.966820 tok/s, one card).
These historical decode numbers are not 512-token results. New prefill and
full-completion measurements remain pending.

Each proposal contains two fresh-load rows. Each row loads once, runs one
512-input-token prefill request, then all twelve registered realistic prompts
once with a 512-token response cap. Every request resets the full request state;
there is no prompt, KV, response or history reuse. Natural EOS ends a response;
otherwise generation reaches the cap. The second row compares every emitted
token, including the prefill response, with the first fresh load.

Choose **either** the two-card A proposal **or** the two-card B proposal. Do not
run both alternatives. The one-card proposal uses A and reserves the whole
host. Two-card A reserves the whole host; B requires the whole host empty at
entry and refuses an A overlap throughout the measurement. All output names
are fresh. These are proposals, not queued work.

## Inputs and measurement definitions

The prefill method comes from
[`bench-prefill-followup.py`](../../../qwen38-27b-b70/scripts/bench-prefill-followup.py)
(`tokens_for`, lines123–137): tokenize real text without adding special tokens,
then take exactly the first512 token IDs. The source is the first prose item
from the frozen
[`2026-09-13-prefill-followup-corpus.json`](../../../qwen38-27b-b70/data/2026-09-13-prefill-followup-corpus.json).
It contains no repeated padding and is distinct from the fixed realistic suite.
`inputs/prefill512/` vendors the text and numeric IDs. The official tokenizer
also reproduces all twelve existing registered token sequences exactly;
[evidence/prefill-input.json](evidence/prefill-input.json) records source hashes.
No model tensor payload was read to construct these inputs.

Prefill is **512 / elapsed seconds**, one user. The native timer starts at the
prompt loop and ends at the first generated token, including the final prompt
position and output head, excluding model load and reset. This follows the
lab's input-token/server-prefill-time convention; it is not HTTP TTFT. The
packet reports request TTFT separately. The first request can include first-use
kernel work; there is no artificial prompt warmup.

The primary decode metric is the median of class medians of
**99 / (timestamp100 − timestamp1)**. The six registered classes and all twelve
prompts are required. Reports retain the event count, interval count, numerator,
endpoints, all-prompt median, mean, p10, TTFT, wall rate, input/output hashes and
all token timestamps. Full natural completion uses all non-EOS generated events,
(N−1)/(tN−t1); cap-limited completions are reported separately. Wall throughput
is emitted tokens divided by request-end minus request-start, including prompt
reading and the complete generation tail.

## Exactness boundary

The unchanged target arithmetic is `iq3-p49-split32-v1`; context4096 and BF16 KV
remain unchanged. Every available packet49 oracle token is checked in-run.
The registered oracle covers128 output tokens. Longer outputs are **not
oracle-exact**: after a matching second fresh load they are labeled
**determinism-checked only**. The independent full-output oracle quality gate
and no-quality-loss decision remain false. No result is submission-eligible.

The existing CPU oracle run took over six hours. Extending all twelve prompts
to512 was not feasible in this75-minute preparation task; no model reads or
partial long-oracle claims were substituted. A complete strict512 performance
workload can pass independently of the unfinished full-output quality gate.
A prompt ending before100 events cannot supply the required primary window.

## Engine and preparation checks

Both packets vendor their runtime source, exact selection, dispatch, inputs,
rotary constants and oracle128 outputs. Native builds reuse every original
compiled kernel object by hash. The only entry changes are cap admission128→512,
one-card suite admission12→13, private paths, and a pre-device `--help` branch.
`measurement-admission.patch` shows the complete source delta; the old
`response-cap.patch` is the earlier cap-only preparation artifact.
`evidence/identity-check.json` reverses every allowed edit and verifies the
original source hashes and unchanged kernel objects. No arithmetic kernel,
selection or bank geometry was changed.

CPU probes compile the actual device entry without `OWN_RT_HOST_ONLY`, replace
only transport/weight payload access with CPU markers, and exercise production
allocation/preparation/issue paths. One-card includes resident lookup preparation
and first-decode sites. Two-card exercises both ranks at positions0,1,511,512.
They run in the real loader environment, with Landlock granting only libraries,
exact metadata/constants and private scratch. GPU nodes and model files are not
granted. These probes validate preparation and parser compatibility, **not GPU
arithmetic, driver behavior or speed**. Peak measured probe RSS stays below4GB.
Every actual native flag is checked against its built binary's real `--help`.
Device-path imports are checked under both A/B masks where applicable.

The analyzer reproduces both historical primary rates from real parent receipts.
Separate synthetic512 tests exercise the final report writer, EOS/cap handling,
full-suite requirement, cache refusal, malformed streams, oracle mismatch and
fresh-load mismatch. Synthetic results are never performance evidence.

The shared `ops/rehearse_entry.py --report` runs the real entry and report path
on its fixed64/128 synthetic fixtures. Those remain strict512=false. Its generic
preparation subcheck warns because it accepts only rank argv and small JSON/TSV
metadata (plus a hard-coded older rotary path); it cannot admit the one-card
argv or these private4MB rotary constants. The separate sandboxed probes above
cover that preparation path. Shared storage, deadline, ELF, loader and report
checks must pass; warnings are retained in the receipts.

## Budgets and shutdown

Device free-space floor:25GB. CPU preparation stop:27GB. Native operation waits
are600s; the two-card controller waits1200s. The recorded conservative cold-phase
floor is60s (native margin10×); observed parent request prefill maxima are also
retained. Load/window watchdog7200s. There is no wall-clock deadline for proving
a stream exists: completed streams are checked after publication/close. No
restart or retry is automatic. Stops use SIGTERM and retain ownership if drain
is incomplete; no hard-kill or reboot path is added.

`budget.json` records measured parent file sizes and explicitly projected512
writes: all128-output bytes scaled4× and13/12 requests, plus fixed raw-state peak
or the measured one-card driver cache. Reservations are2× that scaled estimate
(below the3× planning multiplier), not claims of measured512 writes. The planned
per-load reservations are1,222,788,768 bytes (two-card) and57,141,252 bytes
(one-card). Each later load must pass free-space admission again.

## Rebuild and retained evidence

CPU commands use `nice -n19 taskset -c8-15,24-31 python3 -B`, stdin `/dev/null`.
Compilation and preparation probes take `ops/compile_turn.py` turns and wait
out protected timing work. Native binaries, objects, caches and scratch are
local build artifacts under each packet's ignored `build/` directory.
`lineage/build-inputs.json` pins every original object and contains the exact
private compile/link argv; a restoration script is supplied alongside it.
This is a local lab packet, not a published standalone recipe.

The two4MiB `rope.bf16` files are intentionally retained: each engine embeds
its own private source-relative path, and these exact constants are required
without a mutable cross-packet runtime dependency. Restore them from their
pinned parent paths in `runtime-constants.json`; verify hashes before use.
All previous packets and shared `ops/` implementation files remain untouched.
See the dated [work note](../../../../notes/2026-10-19-own-runtime-packet163.md)
and the final readiness markers for the completed gate receipts.
