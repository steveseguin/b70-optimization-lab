# Packet56 offline submission preparation

`packet56_submission.py` is a packet-local extension of the repository's
packet49 evidence builder. The protected packet49d chain seals the shared
`scripts/packet49_submission.py`, so that file and its shared pin file are
unchanged. This helper uses the same packet49 CPU oracle and pinned current
`scripts/packet49_record_threshold.json`; it never hardcodes a fresh record
floor. Local lineage pins additionally bind the calibrated prefix selection
and generated C++ configuration, and every device window must carry both
hashes. No model/device/network operation is performed by this helper.

After the packet56 CPU seal is complete, the sealer calls
`pin_resealed_packet56(repo=ROOT)`, writing only packet56's
`submission-pins.json`. Do not include this generated pin in its own source
seal, because it contains the seal digest.

After the coordinator finishes the full registered chain:

```sh
nice -n 19 taskset -c 4-15,20-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet56-draft-prefix/packet56_submission.py \
  --packet packet56-draft-prefix \
  --chain /home/steve/own-xpu-runtime-results/packet56-draft-prefix/build/device-cards01-a \
  --output experiments/own-xpu-runtime/stage2/packet56-draft-prefix/submission/prepared
```

The command refuses incomplete, nonexact or slower evidence before writing
eligible output. It creates a portable evidence bundle, result, attestation,
human-readable packet and locally validated payload queue. The inherited
128-token exception remains explicit; the strict 512-token gate stays false.
Posting preflight reads the current pinned record again, so a queue prepared
before another result wins cannot submit against its obsolete floor. Historical
evidence replay retains its original comparison for reproducibility.

The shared external submission validator does not yet recognize packet56's
local dynamic pin directly. `submission_cli.py` loads the **unchanged** shared
CLI with the packet-local lineage validator as its evidence dependency. All
shared preflight, API field checks, quality requirements and posting code still
run. This allows the coordinator to validate and later submit without changing
any file protected by packet49d. Validate offline first:

```sh
nice -n 19 taskset -c 4-15,20-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet56-draft-prefix/submission_cli.py \
  --payloads experiments/own-xpu-runtime/stage2/packet56-draft-prefix/submission/prepared/payload-queue.json \
  --dry-run
```

Then the coordinator runs the same command with `--server-dry-run` in place
of `--dry-run` for authenticated server validation. Real submission follows
only after complete qualifying device evidence and review, using the same
wrapper without either dry-run flag. This task
performs no network call or external submission. A synthetic complete queue
passes the unchanged shared preflight through the wrapper; tampering with the
local seal pin makes that same preflight refuse it.

Local synthetic tests cover the complete evidence derivation, current floor,
changed prefix/config refusal, window binding, missing threshold, local pin
writer, and queue replay. They use no devices or real result fabrication.
