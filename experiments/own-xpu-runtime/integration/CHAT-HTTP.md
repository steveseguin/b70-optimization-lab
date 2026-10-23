# Experimental local chat HTTP adapter

## Question and identity

Can an already admitted `ChatService` expose a small, bounded local HTTP
interface without taking ownership of model startup, checkpoint policy or
shutdown? [chat_http.py](chat_http.py) attaches that service through
`make_server(service, address=('127.0.0.1', 0))`, returning a serial standard
library `HTTPServer`. The caller controls its normal serve/shutdown lifecycle.
There is no executable launcher or native process action in this module.

## Outcome

The only routes are `GET /v1/models`, `GET /health` and
`POST /v1/chat/completions`. Chat requires `Content-Type: application/json`
(optionally `charset=utf-8`), one Content-Length and one `X-Ownrt-Session`.
A session is an ASCII letter/digit followed by up to 38 letters, digits,
underscores, dots or hyphens; the `.lock` suffix is refused. It is a session
component, never a caller-supplied checkpoint path. The server generates a unique
request ID from its UUID namespace and monotonic counter.

Responses use HTTP/1.0 and close the connection. Only literal `127.0.0.1` binds
are allowed. The serial listener accepts at most one request at a time; it does
not create a model queue or concurrently enter the owner.

## What worked

Fifteen tests use actual loopback sockets and a synthetic service. They cover
valid completion and catalog/health routes, unique request IDs, malformed IDs,
duplicate/ambiguous lengths, transfer encoding, malformed or incomplete bodies,
nonfinite/duplicate JSON, nesting, runtime failure, draining, and client resets.
Both body reading and request-line/header reading have a total five-second
deadline. The socket idle timeout is at most five seconds. Headers total at most
65,536 bytes; bodies at most 524,288 bytes; JSON depth at most 64.

Client-input refusal returns generic 400 and leaves intake usable. A runtime
failure returns generic 503 and permanently halts this listener's chat intake;
it does not retry, stop, restart or drain the model. A native front already
outside its ready state is unavailable. `/health` reports that condition with
503 and no private error details. Catalog metadata remains readable.

A disconnected HTTP client does not cancel an in-flight completion or undo its
normal SAVE/RELEASE disposition. The socket test deliberately resets a client
while the mock service completes, verifies the save still happens, and verifies
subsequent normal intake. There is no delivery guarantee or retry deduplication.

## What failed or remains uncertain

The first CPU test run revealed that imported Python recursion settings could
allow deeply nested JSON through the decoder; an explicit depth check now
refuses it before the service. The [failure receipt](receipts/chat-http-first-cpu-failure-20261023.json)
retains the prior source hashes and exact recovered source/test bytes plus the
full 167,357-byte failure log under `lineage/chat-http-first-cpu-failure-20261023/`.
Both recovered source hashes match the original pre-fix receipt. No independently
hashed pre-header-fix intermediate snapshot was retained; that limitation is
recorded explicitly. Independent
review also found inherited HTTP header reads only had an idle timeout; the
bounded header reader and a dribbling-client regression close that gap.

This is experimental, local-only and unauthenticated. Local callers share the
coordinator's checkpoint root and can choose the same session names. Loopback
binding is not authorization or isolation from other local users. Do not expose
it through a proxy or treat this as a complete OpenAI-compatible server.
`ChatService` owns deterministic text-only field validation; streaming, tools,
multimodal input and arbitrary sampling are unsupported. No live native HTTP
probe, model execution or serving qualification is claimed by these socket tests.

## Evidence and patches

See [socket tests](test_chat_http.py),
[CPU receipt](receipts/chat-http-cpu-20261023.json) and
[test log](receipts/chat-http-cpu-20261023.log). All changes are additive;
sealed p197/p198 inputs and transports remain unchanged.

The [joined replay tests](test_chat_http_replay.py) additionally connect actual
loopback HTTP to the real `ChatService`, `Parking` construction and
`PinnedChatCodec`, using the retained device fresh-A and fresh-B token replies.
The replay owner verifies exact recorded inputs before returning those IDs;
this does not execute Parking's real save/restore path or a native owner. The two
CPU tests compare complete HTTP responses, token round trips and usage
(87 prompt/256 completion tokens for A; 60/128 for B), and reject four invalid
sampling/streaming options before any replay-owner call. See the
[join receipt](receipts/chat-http-replay-cpu-20261023.json) and
[join log](receipts/chat-http-replay-cpu-20261023.log). Run this test with the
existing `/home/steve/.venvs/vllm-xpu/bin/python` for the pinned codec dependencies.

```bash
nice -n19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/integration -p test_chat_http.py -v
```

## When to revisit

A coordinator must independently admit the native owner, matching codec,
checkpoint store and parking budget before attaching a real service. Any actual
native HTTP probe needs separate reviewed launch/admission and result evidence.
Authentication, durable request deduplication, concurrency and external binding
would be separate designs rather than changes to this experimental contract.
