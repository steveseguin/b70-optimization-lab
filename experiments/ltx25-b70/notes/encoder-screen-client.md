# Inactive bounded encoder client

[run-encoder-screen.py](../scripts/run-encoder-screen.py) is prepared for the
new encoder runtime packet. It has not submitted any GPU request. It contains
no launcher, shutdown, retry or server replacement action.

The fixed maximum is 25 sequential requests: control, crop, small_state,
combined, then control again; five requests per arm. Each arm uses boat
initialization, boat, marble, bird, boat. Initialization is reported separately
and excluded from the four warm timing samples. These are one-process screening
observations, not a promoted speed or streaming result. Every completed request,
including initialization, must match all four protected original output tensors.

The client requires an explicit packet manifest hash and new server-run path.
Before and after each request it verifies the complete packet, startup runtime
fingerprints, model receipt, PID/start ticks/boot identity, extension and launcher
hashes, argument hash, exact endpoint-versus-file identity, idle queue, fault
latches, disk space and available host RAM. It never substitutes the historical
PID into a new identity. A nonblocking client lock prevents overlapping runs of
this client against the same server-run directory.

Prepared graph templates must equal the frozen selected graph except for the
encoder variant and diagnostic node421, which receives node364 conditioning and
feeds both node365 conditioning inputs. Geometry, frame rate, sampling schedules
and all other operations remain frozen. The profile client assigns unique output
names; diagnostic names are assigned to the same request. Candidate receipts
must establish the expected native small-state census, individual BF16 placement,
option state and accounting. Between arms the client checks the component
generation and the previous encoder's unload receipt, including CPU placement,
registered owner identity and cleared accounting.

The existing profile and four-tensor comparison helpers are used unchanged
through sequential subprocess calls and pinned hashes. The existing stability
helper supplies memory snapshots, capture validation, file inventories and
verified retention. Only this campaign's explicitly registered files can be
deleted. Passing comparison, placement and unload gates precede deletion of raw
archives; a maximum of three passing review MP4s remains. Protected references,
metadata, inventories, exactness receipts and failure footage remain intact.

Failures stop new submissions without server control. A client deadline does
not imply that server work stopped; the failure record tells the operator to
inspect the existing process. Failure-stage metadata preserves earlier passed
rows when a later preflight fails.

[Eight CPU tests](../scripts/test-encoder-screen.py) passed, including a simulated
full 25-request flow, failed comparison retention, next-request preflight failure,
quality-floor mutation rejection, identity mismatches, individual placement and
unload ownership/accounting checks. The [receipt](../data/encoder-screen-client-cpu.json)
and [log](../data/encoder-screen-client-cpu.log) are CPU test evidence only.
All simulated output bytes and timings are fabricated fixtures, never benchmark
measurements. Endpoint communication, real runtime placement and native-model
comparison remain untested by this client.

The eventual invocation, only after the corresponding server is already
running under its verified packet, is:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python \
  experiments/ltx25-b70/scripts/run-encoder-screen.py \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-PACKET \
  --manifest-sha256 EXPLICIT_MANIFEST_SHA256 \
  --server-run /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-RUN
```

The placeholder packet/run names must be replaced with actual reviewed paths.
The client cannot launch that server, resume an interrupted campaign, select
additional arms or expand the 25-request limit.
