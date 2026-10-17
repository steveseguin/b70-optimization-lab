# Packet64 submission preparation

The packet-local tools mirror packet61x. The floor is read from
`scripts/packet49_record_threshold.json`, validated against its ledger and
checked again before posting. There is no private lower floor.

After the full registered chain passes:

```bash
P=experiments/own-xpu-runtime/stage2/packet64-record-bundle
OUT=/home/steve/own-xpu-runtime-results/packet64-record-bundle/build/device-cards01-a
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/packet56_submission.py" \
  --packet packet64-record-bundle --chain "$OUT" --output "$P/submission/prepared"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/submission_cli.py" \
  --payloads "$P/submission/prepared/payload-queue.json" --dry-run
```

If an explicit resume registered a new destination, OUT must be that destination.
The builder rejects other chains. It binds the combined executable, active
selection, screen and chain seals, prefix configuration, retained exactness,
fresh owners, placement and lane-admission sidecars. Offline replay uses the
collected exact sidecar bytes. Timing rows require the whole-host admission proof.

Payload notes name the draft-head prefix, controller spin and pure-spin waits,
HC fusion and actual layer split. Draft-HC kernels and batched rollback copies
are described only if selected. No bank/overlap option is accepted. Tests cover
all eight payload variants, changed selection/proof rejection and the current
record floor.

The inherited record path is explicitly the 128-token suite. Its strict
512-token realistic final gate stays **false**. A screen or CPU gate cannot
qualify, and no prefill or natural-completion number is invented. Preparation
has not posted or attempted to post a result.

After reviewing complete qualifying evidence, the coordinator can run the
shared server validation and posting path:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/submission_cli.py" \
  --payloads "$P/submission/prepared/payload-queue.json" --server-dry-run
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/submission_cli.py" \
  --payloads "$P/submission/prepared/payload-queue.json"
```

The second command posts externally. Following an actual successful response:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/packet56_submission.py" \
  --update-record "$P/submission/prepared/result.json" --submission-id "$SUBMISSION_ID"
```

Commit the real result and updated ledger together; do not run publishing in
parallel with the owner.
