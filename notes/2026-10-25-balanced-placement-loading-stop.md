# Balanced placement stopped during loading

The first attempt with cuts 0/8/21/34/48 stopped on stage 0 before readiness,
other owners or requests. Native loading reported `cooperative rank stop` and
exited 1; the controller reported a closed stage channel. No worker remains.
Both the saved observations and a fresh passive check retain the same fourteen
historical fault signatures. No new GPU fault, reboot or driver reset occurred.

The original reason is unknown. The controller's watcher validates observations
before recording them, and its terminal handler can replace an already-latched
guard reason with the later socket error. The next change retains that first
reason and rejected observation without relaxing any safety check. This is a
diagnostic correction, not a claim that the underlying stop cause is fixed.
A later distinct attempt may proceed only with reviewed diagnostics and a new
admission; this is not an automatic retry.

[Failed-run archive and original source hashes](../experiments/own-xpu-runtime/research/continuation-2026-10-25/persistent-balanced-qualified-a-stop-archive.json)
preserve all 57 members with an independently rehashed durable copy. No prompt
was executed and no performance number exists. The extracted-source CPU build
started after this run had already stopped, so it did not cause this stop.
