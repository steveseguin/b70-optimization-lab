# Streaming v1: CPU components and integration

This directory adds token-time observation, stable incremental text decoding,
a streaming chat service and a serial loopback SSE adapter around the unchanged
protocol-v2 owner. The assembled Python stack passes64 CPU tests; native execution
and production lifecycle admission remain separate gates. See
[the current CPU closeout](CPU-CLOSEOUT.md) for all components and evidence.
Packet197–200 sources and canonical integration modules remain unchanged.
The engine/decoder design and its original29-check scope are described below.

`engine.StreamingCheckpointEngine` subclasses the canonical checkpoint engine.
Only `generate` and `run_turn` are narrow copy-and-delta methods adding optional
`on_token=`. The exact supplied front and store objects remain installed; no
native method, process, load, lock ownership or checkpoint identity is replaced.
The existing `RunAdmission.front` proxy already forwards callback keywords to
the canonical `NativeFront.request`. The same owner mutex spans policy lookup,
generation and SAVE/RELEASE. Same-ID/no-save outcomes still RELEASE, including
the final request.

The callback runs when the native token frame is read, before RUN completes.
It must perform bounded trusted work: local decoding/queueing or the reviewed
delivery component's bounded nonblocking socket sends. Arbitrary callbacks are
not made nonblocking by this engine. The first callback exception disables
further callback calls, retains the original exception in
`engine.last_observer_error`, and allows native parsing plus normal disposition
to finish. The returned `observation` contains `enabled`, `observed_tokens`,
`callback_calls_completed`, `observer_failed`, and bounded error metadata.
These count callback completion, not wire delivery. The SSE layer must consult
its delivery status separately and must not publish successful final/DONE after
an observer or delivery failure. Native, SAVE, policy and frame-parity failures
retain canonical poisoning and ownership behavior; they are never retried or
turned into an automatic RELEASE.

`decoder.TokenDecoder(codec, maximum_tokens=512)` requires the exact canonical
`PinnedChatCodec`. `feed(token_id)` returns an immediately stable text delta;
`finish(expected_tokens)` flushes a possible incomplete UTF-8 suffix and checks
the concatenated output against one complete canonical decode. It uses the
pinned tokenizer's actual byte mapping, not repeated full-decode slicing.
The incremental UTF-8 decoder uses `errors='replace'`, matching the canonical
whole-reply behavior. An incomplete multibyte sequence emits nothing until its
continuation or final flush. Whitespace, combining marks, malformed bytes and
nonterminal special tokens are preserved. Only a final admitted terminal ID
is suppressed from display; the original token list retains it for history and
usage. Any later token after that terminal is a decoder error.

The exhaustive admitted-vocabulary census gives a maximum of 128 bytes per
token. The decoder enforces that limit and at most512 tokens: at most65,536 raw
bytes, or196,608 UTF-8 bytes after worst-case replacement. No decoder buffers
grow with connection lifetime. Streaming finish/stop policy and postreply
success still belong to the service/coordinator.

The original identities are explicit:

| Source | SHA256 |
| --- | --- |
| [Canonical engine](../checkpoint_engine.py) | `5bee78743a8c98c3dd24af0703de429cf0e1ede0b0fb9a772bb3c624be581295` |
| [Canonical codec](../chat_codec.py) | `20c0fac1f268eaa2f95b6c86a266e906b92008537f3de157a7e3279d3b74909b` |
| [Canonical transport](../request_front/client_v2.py) | `d316cf76bf66bf891a19c9cf01300028c1ba08950ec7d9949bf5970e70635f0b` |
| [Tokenizer byte mapping](../../../qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/tokenizer.py) | `1c284c06b6a159c39cb9a00acd7cc411ed9adae87b4850e98da5dd4fd33543a7` |

Twenty engine tests include all13 canonical regressions and genuine precompletion
callback timing, callback exceptions through SAVE/RELEASE, final disposition,
native-error precedence and frame mismatch. Nine decoder tests use the actual
pinned codec (only its10.95MB GGUF header, no weight loading), all six retained
packet199 replies, arbitrary Unicode/subword pieces, all256 byte tokens and
malformed UTF-8. Synthetic native/store tests do not claim device execution.
Source hashes, commands and logs are retained in [cpu-seams.json](cpu-seams.json).

The engine/decoder checks alone do not qualify native model streaming or serving
performance. The additive service and HTTP adapter enforce terminal success after
complete token validation and SAVE/RELEASE, and preserve exact native stop IDs
`{248044,248046}` and usage including the suppressed final ID. Their separate
CPU replay/socket evidence is linked in the current closeout; it does not assert
a live model, native streaming owner or production lifecycle qualification.
