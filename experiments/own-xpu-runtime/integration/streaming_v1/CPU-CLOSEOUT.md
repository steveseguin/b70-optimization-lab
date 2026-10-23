# Streaming replies: CPU components and composed socket tests

## Question and identity

Can the existing native token callback produce stable text as tokens arrive,
while preserving deterministic output and checkpoint disposition? These additive
modules use the unchanged protocol-v2 front, pinned checkpoint engine and actual
GGUF tokenizer byte mapping. No packet197–200 source is modified.

## Outcome

**64 CPU tests pass**, repeated together by the root in 4.261 seconds:20 engine
checks (including13 canonical regressions),9 decoder,9 delivery,13 service,
8 HTTP and5 composed-stack checks. Every component and the composed socket
suite has independent review. No native owner or model inference ran for these
checks; the real codec reads only its pinned10.95MB GGUF header.

## What worked

The engine forwards observed tokens during RUN. A callback exception disables
further observation, retains the original error and allows native parsing plus
SAVE/RELEASE to complete. Native and storage failures keep the original halt
semantics. Incremental UTF-8 decoding preserves stable prefixes across split
characters, malformed byte pieces, whitespace and special tokens. The full text
must match the canonical decoder; only a final admitted stop ID is hidden from
display, while token history and usage retain it.

The transport borrows an exclusively owned nonblocking socket. Its64KiB queue,
1MiB total cap and bounded send calls prevent a slow reader from blocking native
callbacks. Overflow or disconnect abandons delivery. A final drain of at most
one second is permitted only after disposition. This proves local socket
acceptance, not peer receipt.

The serial loopback endpoint supports `stream:true` and ordinary responses.
It emits role/content chunks before generation finishes. Finish reason, usage
and `[DONE]` are emitted only after the service validates the whole response
and completes SAVE/RELEASE. Failed native work halts intake without false DONE.
Invalid client options remain a JSON400 refusal before SSE headers/native RUN;
a halted runtime retains503 behavior.

The composed tests use the actual service, engine, codec and HTTP modules with
an intercepted native front/store. All six recorded p199 replies match their
ordinary HTTP text, exact consumed prompts and usage. Separate checks hold SAVE
and RELEASE at explicit barriers to verify DONE ordering, exercise bytewise
Unicode, preserve disposition after a reader reset, and refuse false success
after an ambiguous SAVE failure.

## What failed or remains uncertain

Independent review found two transport details: per-send MSG_DONTWAIT is needed
to survive a sequential blocking-mode change, and Python's positive timeout must
be refused before send because it performs its own readiness wait. The caller
must exclusively lend the socket; concurrent timeout mutation is outside this
contract. HTTP review also restored the canonical distinction between client
errors and a runtime that has already halted. Prior candidates and fixture
failures remain in `lineage/`.

The original lifecycle requires the exact nonstream server type and deliberately
rejects the new server. No production composition or live admission is claimed.
The existing tiny HOST_ONLY owner also has a synthetic16-token vocabulary and
cannot satisfy the real codec/service identity. Its proposed protocol proof
must use an explicitly synthetic facade, without weakening either gate. See
[the host-only plan](HOST-ONLY-PLAN.md).

## Evidence and patches

- [Root64-check gate](receipts/root-cpu-gate.json) and [test log](receipts/root-cpu-gate.log).
- [Engine/decoder review](receipts/engine-decoder-review.json),
  [delivery review](receipts/delivery-review.json), [service review](receipts/service-review.json),
  [HTTP review](receipts/http-review.json), [composed review](receipts/composed-review.json).
- [Engine](engine.py), [decoder](decoder.py), [delivery](delivery.py),
  [service](service.py), [HTTP adapter](http.py), [composed tests](test_composed.py).

Run the tests as package-qualified modules with the integration directory on
PYTHONPATH. Direct discovery with `-s streaming_v1` can put its `http.py` ahead
of the standard-library `http` package; that fixture invocation failure is
retained in the composed CPU receipt. No module alias or global import override
is used to work around it.

## When to revisit

Complete one independently reviewed tiny HOST_ONLY callback/disposition/SSE
proof without model or GPU execution. Its scope remains synthetic. Then build a
separate admitted streaming lifecycle/composition and a small exact device
comparison. Preserve the existing baseline, full BF16 state, fault-halt behavior
and single-attempt application window rules. These CPU results do not justify
streaming performance, general hosting or a new benchmark submission.
