# Packet56w submission tooling

The local `packet56_submission.py` mirrors packet56's evidence builder and
adds the packet56w chain and screen-seal pins. Its payload notes explicitly
name both the 91,392-row draft-head prefix and bounded 250 µs controller spin,
including the rank-0 queue profiling property. The target keeps its full head.
This is a combined spin/queue-property candidate, not a causal claim for spin
alone. No screen result is eligible for this helper.

Run only after the full coordinator chain succeeds. From the repo root:

```bash
P=experiments/own-xpu-runtime/stage2/packet56w-chain
OUT=/home/steve/own-xpu-runtime-results/packet56w-spin/build/device-cards01-a
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/packet56_submission.py" \
  --packet packet56w-chain --chain "$OUT" --output "$P/submission/prepared"
```

This offline command replays exactness, fresh processes, oracle and build
identity, fault tails, timestamps and metric accounting from bound original
receipts. It reads the current pinned record floor; it refuses incomplete,
changed, nonexact or slower evidence before writing an eligible payload queue.
The 128-token exception remains explicit and the strict 512-token gate is false.

The local CLI loads the unchanged shared submission implementation with this
lineage validator. The coordinator runs these in order after preparation:

```bash
P=experiments/own-xpu-runtime/stage2/packet56w-chain
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/submission_cli.py" \
  --payloads "$P/submission/prepared/payload-queue.json" --dry-run
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/submission_cli.py" \
  --payloads "$P/submission/prepared/payload-queue.json" --server-dry-run
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/submission_cli.py" \
  --payloads "$P/submission/prepared/payload-queue.json"
```

The last command posts a real result. None of these commands has been run
against real packet56w chain evidence by this preparation. Posting preflight
checks the current record again, so a superseded queue cannot use an obsolete
floor. Historical bundle replay retains its original comparison.

After the coordinator receives a successful real submission ID, record it:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/packet56_submission.py" \
  --update-record "$P/submission/prepared/result.json" --submission-id "$SUBMISSION_ID"
```

That explicit follow-up updates the shared record ledger, so the coordinator
must commit its result and ledger together. Preparation changes no shared floor,
shared submitter or parent's submission pins.
