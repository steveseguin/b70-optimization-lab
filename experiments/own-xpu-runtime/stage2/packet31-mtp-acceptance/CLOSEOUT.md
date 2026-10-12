# CPU MTP acceptance — closeout

<!-- campaign-closeout -->

## Question and identity

Measure guesses for the Unsloth IQ3 target, revision 766911a6b7369840a91dbcd95f9f997acaab6cd6,
arithmetic iq3-p17-detmath-v2. The official MTP source is revision
bcd9f01ddc9cff2316eb84281bebcd5b058bddce. Four development prompts, 64 generated
tokens each, on steve-b70s using only CPU execution, nice 19 and idle I/O.

## Outcome

The primary FP8-semantic CPU draft with IQ3 bindings hit 198/256
(77.3%). This is measured CPU draft acceptance, not device
speed or a certified served-device draft identity. All 64 incident target
tokens and eight retained final-stream fixtures matched the sealed v2 oracle.
See the [complete tables](README.md) for every variant and prompt.

## What worked

The independent source review established shifted MTP/cache positions, global
hidden normalization, Gemma offset weights and complete prompt history.
The frozen CPU target supplied every position without using a device.
[Target gates](target-gates.json) and [per-position results](acceptance.json)
retain the checks and controls.

## What failed or remains uncertain

The old packet2 reference could not be used unchanged: its norm conventions,
FP8 activation path, weighted-down boundary and BF16 gates required correction.
CPU/device arithmetic parity remains unverified. Int8 requires a new loader;
shortlists have no measured device cost. Four development prompts do not
establish broad-task or long-context acceptance. No scheduling implementation
or target-state rollback was tested. No runtime change was adopted.

## Evidence and patches

[Build receipt](build-receipt.json), [independent review](wiring-review.md),
[measurement plan](measurement-plan.md), [target evidence](target-evidence.json),
and [reproduction](reproduce.sh). The packet contains only measurement tools.
[Cleanup](cleanup.json) records scratch removal; raw streams and binaries can
be regenerated, while stream hashes and complete token evidence remain tracked.
No historical XPU-kernel payload was recovered for a device parity oracle.

## When to revisit

After a separately admitted device implementation has complete draft caches,
operator parity, bounded weight/head residency and discardable speculative
target state, measure its latency and acceptance against this capture and a
broader fixed suite. Keep every emitted token verified by the unchanged IQ3
target. Any device window remains the coordinator’s work; this packet grants
no device admission.
