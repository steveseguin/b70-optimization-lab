# Packet201 exact mixed streaming result

## Question and identity

Can the tested native runtime deliver incremental text without changing the
ordinary sixteen-turn serving result or state disposition? This run used the
unchanged p198 one-card ELF, full BF16 state, context 4096 and a 21,552,729,600-byte
expert cache. The root manifest is
`7d0eceb06516995ba6ab0876d9a439aef5ef920c879afe2da7a3ab0f16549383`;
canonical plan is
`85f3e70a071dee9438fab957f0bc98593175954323820b88718c7084d8030bad`.
Model, quantization, cache and arithmetic identity match the prior serving pilot.
This is serving qualification, not a cold-speed or LocalMaxxing record.

## Outcome

One loaded owner completed 16 RUN and 16 SAVE dispositions, producing exactly
1,484 tokens. All sixteen consumed prompts, output sequences, displayed text,
finish reasons and usage match p200. Seven responses used SSE and nine ordinary
JSON. Five older full-length token oracles and one resumed/fresh token pair also
match. All seven raw SSE streams independently replay with complete terminal
sequences, and each client received text before its finish frame.

The native owner exited 0 at its 16-request limit, with no signal, discarded
pending request or retained resource. Both diagnostic workers joined after EOF;
all 170 stderr bytes were captured with no discard. The two-phase completion
receipts and independent physical drains passed. Restoration as restore30 began
at 21:36:41 UTC. All three applications passed validation by 21:46:18 UTC, and
the controller completed successfully at 21:46:19 UTC.

## What worked

Final A has 128 state blobs and matches the p198 S1 blob/token-state maps; final B
has 128 and matches p199 b-park. All 256 current blobs were independently rehashed.
Current checkpoint extents are 69,121,617 and 64,715,747 bytes. Earlier state was
evicted normally by the parking policy; the resumed/fresh comparison proves
output-token equality but does not invent rehashed equality for deleted states.

The streamed responses retain their exact payload bytes as base64, SHA256 and
bounded complete-frame receipt offsets. Independent parsing checks unique JSON
keys, strict UTF-8, stable response identity, role/content/finish/usage ordering,
one final marker and EOF. The first stream had 256 text frames; the other six
include resumed/fresh conversation, natural stops, JSON and Unicode. Observed
receipt times are neither native generation latency nor a speed comparison.

The initializer recorded 215,788.396946 ms to load and pin, with empty initial
expert-cache content and first-prompt fills charged to that request. This is
initialization evidence only. The conservative launch-origin idle limit was
preserved. No storage, power, clock, memory or swap setting changed for the run.

## What failed or remains uncertain

No runtime mismatch or new fault appears in the retained capture. The known
historical two-fault boot identity remained the admitted authority. The native
raw stdout protocol is not retained; terminal/control evidence is present in
the worker receipts and sixteen native SAVE receipts. Ordinary replies preserve
parsed bodies and original response hashes, rather than raw HTTP bytes.

The independent audit binds actual active worker/client safe-stop observations.
Those observations establish the live unit configuration; they do not establish
terminal exit status. Successful terminal unit status remains attested by the
sealed controller and restore admission, since completed transient units were
collected. No provisional client receipt alone permits restoration.

The monitored 768 MiB worker forecast plus 1 MiB client reserve is not a hard
filesystem quota over all driver writers. Eight short prompts retain exact prior
outputs but have no new independent semantic-quality authority. Native and
checkpoint experimental labels remain unchanged: this result does not establish
broad OpenAI compatibility, portable packaging, concurrent batching, longer
context or a general production-service release.

## Evidence and retention

- [Independent device audit](evidence/independent-device-result.json), binding
  530 artifacts and 141,835,648 bytes, including current checkpoint tensors.
- [Client result](evidence/client-a/client-result.json),
  [worker terminal](evidence/planned-a/output/terminal/worker.json), and
  [pre-completion receipt](evidence/planned-a/output/terminal/pre-completion.json).
- [Active worker/controller properties](evidence/root-active-worker-units.json),
  [active client properties](evidence/root-active-client-unit.json), and
  [post-completion unit observations](evidence/device-unit-observations.json).
- [Raw diagnostic index](evidence/raw-diagnostics-index.json),
  [admission](ADMISSION.md), and [client contract](CLIENT.md).

[Sealed-input retention](evidence/sealed-input-retention.json) distinguishes the
eleven locally generated source/binary inputs from tracked source. Their tracked
p197/p198 overlay and compile-only recipes reconstruct those inputs; exact
admitted digests remain mandatory. One independently verified adapter test log
omitted from the earlier source commit is retained here byte for byte.

Compact native summaries, raw SSE captures, protocol/disposition receipts,
checkpoint metadata and tiny token/next-token binaries are tracked. The 256
checkpoint tensors remain at their recorded private paths, with current hashes
in the independent audit. Seventy larger diagnostic traces are retained locally
and indexed by path, size and SHA; driver caches are not promoted. The full
roughly 2.4 MB kernel capture is intentionally retained permanently in Git to
reconstruct fault scope for admission and teardown. Its consumers are the fault
review and independent result audit; restore exact historical bytes with
`git show <result-commit>:experiments/own-xpu-runtime/stage2/packet201-streaming-serving/evidence/planned-a/output/control/kernel.jsonl`
into a separate review file. Never strip whitespace from original native TSV,
process-status or kernel evidence to satisfy formatting checks.

## Restoration and next action

[Independent restoration review](evidence/independent-restore30-review.json)
passed. Twelve compact ready/completion/validation files (20,415 bytes) are kept
under [restore30](evidence/restore30/copy-receipt.json). Captured live service
PIDs/configuration and safe-stop properties match those records. Final observations
at 21:46:56 UTC confirm the same boot and two known historical faults, memory
blocks 53–56 offline with the known block57 exception unchanged, original PAUSE
bytes, empty queues, no STOP/inflight state and 28,451,844,096 bytes root free.

The attach-only chat CLI has separately passed 17 CPU checks and independent
review; it was not the client used in this device window. The next speed lever
is true prefill/chunk processing. [Closed-run timing analysis](../../integration/streaming_v1/P201-PREFILL-OBSERVATIONS.md)
attributes 10.790s of a fresh 370-token prompt request's 15.404s native time to
prefill. This motivates CPU-first source/authority work, not a measured candidate
gain. The first-use enqueue stall remains separately unattributed. No new device
window is implied by that analysis.
