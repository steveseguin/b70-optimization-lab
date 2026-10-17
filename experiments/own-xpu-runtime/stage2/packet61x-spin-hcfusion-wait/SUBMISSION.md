# Packet61x submission tools

Run only after the complete coordinator chain succeeds. The local evidence
builder mirrors packet61, binds the packet61x chain and screen seals,
and validates the prefix, pure-spin and HC identity on every model window.
Payload notes name all three changes, including rank-0 queue profiling and all three pure-spin wait paths.
The helper refuses packet61's old 250 µs policy and packet56x sleep20 identities.

The floor comes from `scripts/packet49_record_threshold.json`, currently
46.96269702286488 tok/s, and is checked again before posting. The helper refuses
incomplete, changed, nonexact or slower evidence. Screen results cannot qualify.
The owner-authorized 128-token scope stays explicit; the strict 512-token gate
remains false. No prefill or natural-completion result is invented.

```bash
P=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
OUT=/home/steve/own-xpu-runtime-results/packet61x-spin-hcfusion-wait/build/device-cards01-a
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/packet56_submission.py" \
  --packet packet61x-spin-hcfusion-wait --chain "$OUT" --output "$P/submission/prepared"
```

After preparation, the coordinator runs:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/submission_cli.py" \
  --payloads "$P/submission/prepared/payload-queue.json" --dry-run
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/submission_cli.py" \
  --payloads "$P/submission/prepared/payload-queue.json" --server-dry-run
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/submission_cli.py" \
  --payloads "$P/submission/prepared/payload-queue.json"
```

The last command posts a real result. Preparation has run none of these
against real packet61x evidence. After receiving a successful submission ID:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/packet56_submission.py" \
  --update-record "$P/submission/prepared/result.json" --submission-id "$SUBMISSION_ID"
```

That explicit action updates the shared record floor. Commit its result and
ledger together. Packet61x preparation does not edit any shared submission file
or parent seal. Synthetic tests exercise successful replay, tamper rejection,
current-floor refusal, CLI integration and all three payload descriptions.
