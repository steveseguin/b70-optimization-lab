# Warm native request transport

Packet197's bounded device lifecycle now passes with this v1 transport:
eight requests, one load, exact outputs and checkpoint state, clean shutdown.
See the [device result](../../stage2/packet197-warm-request-front/RESULT.md).
This is not a complete serving qualification or a speed record.

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

The mock's speed and outputs are not model evidence. The device gate
interleaved fresh A, fresh B and restored/appended A in one load and compared
outputs and state against exact references. Checkpoint reuse is outside the
cold record metric. Chat rendering and parking policy are not yet attached.

`client_v2.py` is a separate experimental transport for packet198's postreply
SAVE/RELEASE protocol. It keeps a completed request pending until explicitly
saved or released, including after the final allowed RUN. It validates
operation identities, token-history bounds, manifest receipts and explicit
discard-on-close events. Nine CPU subprocess tests and an independent review
pass; this does not yet establish native compilation or device qualification.
The old client remains unchanged and hash-pinned by packet197.

The [postreply design](POSTREPLY-CHECKPOINTS.md) records the protocol and later
adapter gaps. Inspect/delete and ctxkeeper wiring remain separate work.
