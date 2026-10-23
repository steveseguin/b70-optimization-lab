# Warm native request transport

CPU implementation for the next own-runtime serving step. The native side is
being derived separately in packet197 from the qualified packet181 checkpoint
engine. This transport has not run with a device engine and is not a serving
qualification or a speed result.

`client.py` attaches to one already started native owner through binary pipes.
It accepts sequential token-ID requests, with optional checkpoint restore/save
IDs, and consumes explicit ready, start, token, completion and drain events.
It never starts, restarts or kills an owner. A protocol error, native fault or
deadline stops further requests; the coordinator retains responsibility for
the incident and graceful drain. Stderr belongs in the experiment log.

The wire protocol is `ownrt.request-front.v1`: one tab-separated RUN line with
request ID, response cap, restore ID or `-`, save ID or `-`, and decimal token
IDs separated by spaces. `QUIT` requests final drain. Paths never come from the
client. Result references are scoped to `requests/<id>/result.json` beneath
the owner output directory. Native diagnostics use stderr; stdout is JSONL.

Eight CPU subprocess tests cover multiple requests in one owner, checkpoint
arguments, exact token event order, malformed inputs, duplicate requests,
foreign result paths, native failure/EOF, timeout without killing the owner,
admission geometry, automatic drain at the request limit, and orderly quit:

```bash
python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/integration/request_front -p 'test_*.py'
```

The mock's speed and outputs are not model evidence. Before a device run,
the native overlay must pass its parser, reset, identity and teardown checks.
The device gate will interleave fresh A, fresh B and restored/appended A in
one load, compare outputs and saved state against exact references, and report
loading, restore, prefill and first-token time separately. Checkpoint reuse
is outside the cold record metric. Chat rendering and parking policy attach
only after this token-ID boundary works.
