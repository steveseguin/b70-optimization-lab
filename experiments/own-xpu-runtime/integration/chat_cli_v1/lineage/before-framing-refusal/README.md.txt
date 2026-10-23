# Attach-only experimental chat client

This standard-library client talks to an **already admitted loopback endpoint**.
It starts no owner, model, service, process, checkpoint tool or device work. It
is an experimental client for the current 4096-context serial serving stack,
not a portable serving package or concurrent batching implementation. Its CPU
fixtures replay synthetic native replies; they make no device or latency claim.

From the integration directory, with an endpoint the coordinator has supplied:

```bash
python3 -B -m chat_cli_v1 --endpoint http://127.0.0.1:PORT \
  --model MODEL --session conversation-a --prompt 'Explain this briefly.'
```

Replace `PORT` and `MODEL` with the admitted endpoint values. Omit `--prompt`
for one user turn per stdin line (TTY input shows a prompt); EOF exits the
client. `--ordinary` selects ordinary JSON replies; `--max-tokens` defaults to
128 and accepts 1..512. There is no implicit endpoint discovery, launch,
redirect, model download, retry, server shutdown or restart.

The same explicit session ID accompanies every turn. Real user/assistant text
is retained **only after a fully validated response**, including streaming
role/content/finish/usage/`[DONE]` and EOF. Deltas appear before completion and
are provisional until then. Any failed exchange halts this client interaction,
preserves the original exception and bounded partial response on
`client_partial_response`, and leaves that turn out of history. A terminal
sink failure closes the client response; the server owns its normal disposition.
This client neither attests nor intervenes in native SAVE/RELEASE.

The client accepts at most 16 successful turns, 64 messages and 64KiB of retained
UTF-8 history. Encoded requests also have a 64KiB ceiling. No history is silently
truncated or approximated. Actual token/context admission remains server-owned;
a context refusal is reported as HTTP failure, without automatically trying a
shorter request. History lives only in this process. A session ID alone does
not recover conversation text after restarting the client.

SSE has a 128KiB response cap, 8KiB line cap and at most `max_tokens+4` frames.
JSON replies have a 64KiB cap. Both modes validate the exact response model,
request-ID shape, integer usage arithmetic, context and response cap; SSE also
requires stable IDs/model/created, strict UTF-8/JSON, and one terminal sequence.
A 900-second exchange deadline is refreshed before each bounded header/body
read. Headers have an aggregate 64KiB ceiling. Connection establishment and
request send use the same socket timeout; there is no watchdog thread or claim
to interrupt arbitrary local stdout callbacks. HTTP/1.0's detached socket is
retained for timeout updates, and response plus connection are explicitly closed
while preserving primary failures. Client receipt timing is not model TTFT.

## Provenance and CPU validation

The bounded `read1` SSE parser is adapted from the frozen
[packet201 client](../../stage2/packet201-streaming-serving/client_pilot.py),
with its exact SHA recorded in [parent-pin.json](parent-pin.json). The new copy
adds model, observer and deadline parameters plus retained partial text. It does
not import or modify the qualification client. Transport, conversation/history,
header reader and CLI are local additions. Existing streaming modules are
unchanged.

Run the synthetic socket checks from the integration directory:

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  nice -n 19 taskset -c 8-15,24-31 \
  /home/steve/.venvs/vllm-xpu/bin/python -B -m unittest chat_cli_v1.test_client -v
```

The tests use real `StreamingServer`, pinned codec and streaming engine/service,
with synthetic native/store fixtures. They cover multi-turn ordinary/SSE parity,
byte-split Unicode, live delta before RELEASE and delayed history commit,
context refusal, failed SAVE, sink disconnect, local limits, stdin/one-shot
modes, malformed frames, usage bounds, detached socket cleanup and slow header
and partial-body deadlines. See [CPU receipt](receipts/cpu-tests.json) and
[log](receipts/cpu-tests.log). The original ordinary-response EOF failure is
retained in `lineage/before-ordinary-content-length-eof/`: Content-Length
completion closes the response socket, so the ordinary loop must stop before
attempting another timeout update. A subsequent header-test fixture lacked a
`flush` method; its failure log is retained there too.
