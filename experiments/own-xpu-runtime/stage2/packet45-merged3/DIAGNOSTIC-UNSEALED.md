# Diagnostic unsealed device handoff

Owner directive: October 15, 2026, 01:10 UTC. These commands are for the coordinator's admitted nice-0 device unit, on cores 0-3,16-19, with its existing LD_LIBRARY_PATH. This CPU-only repair session does not execute them. Outputs are diagnostic and can never qualify for publication or submission.

The switch skips exactly four seal provenance checks (passed, source/manifest hashes, receipt memory-plan equality, receipt artifact hashes). Actual artifact bytes are hashed at admission. Fault latch, watchdogs, teardown, priority, memory/storage admission, prerequisite topology, and oracle/token comparisons remain mandatory. Prerequisites must also be diagnostic, from the same boot and actual artifacts. A later metadata reseal does not invalidate such a chain.

From the repository root:

```bash
p=experiments/own-xpu-runtime/stage2/packet45-merged3
out="$p/build/diagnostic-fix5-c4096-dr0"
suite=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
PACKET45_DIAGNOSTIC_UNSEALED=1 taskset -c 0-3,16-19 bash "$p/coordinator_windows.sh" 0 4096 0 "$suite" "$out"
```

After the matching chain prerequisites pass, standalone 128-token exactness and speed windows:

```bash
w=(taskset -c 0-3,16-19 ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$p/window.py" --authorized-device-window --diagnostic-unsealed --card 0 --context 4096 --draft-rank 0 --k0 "$out/K0/window.json" --k1a "$out/K1a/window.json" --k1b "$out/K1b/window.json" --k2 "$out/K2/window.json" --w0p "$out/W0p/window.json" --kd "$out/KD/window.json" --dispatch "$out/K2/run0/dispatch-measured.json" --suite-manifest "$suite" --controller native --repeat 1 --max-new 128)
"${w[@]}" --window WS128x --retain-steps 1-8,97-104 --output "$out/WS128x"
"${w[@]}" --window WS128 --retain-steps none --exactness-window "$out/WS128x/window.json" --output "$out/WS128"
```

Gate evidence: 14/14 new unit tests; one 4096/dr0 diagnostic coordinator chain, 9/9 windows. The final source-stability bookkeeping assertion detected an edit to the normal-only historical-evidence guard during the chain; its original execution hash and the narrow exception are recorded in diagnostic-coordinator-gates.json. No runtime failure occurred, and the chain was not repeated.

No packet-local publish/promote entry point exists. The packet guard and localmaxxing builders/submission/attestation helpers reject diagnostic or explicitly unqualified objects, including nested receipts and bound JSON quality/performance evidence.

After the diagnostic commit, all source and existing build files are frozen. Minimal reseal uses cores 4-15,20-31 at nice19, only metadata checks and small unit/admission gates; production model, compiler matrix and sanitizer runs are reused, never repeated. The two changed translation units are linked into the model binary but are not called by production decode. Historical real-model receipts retain their original identities.
