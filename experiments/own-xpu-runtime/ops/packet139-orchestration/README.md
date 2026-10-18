# Packet139 orchestration — bundle9

This is a new copy. Packet136, its running chain, packet137 and all shared
wrappers remain untouched. Bundle9 selects packet136's banked bundle8 plus
packet137's exact token-input table and fixed target buffers (`both`).

The review26 readiness rule was fixed before bundle9 device data:

- Read packet137 `v5/evidence/device-v5-B`: one model lifetime, five views in
  original/both/original/both/original order. Both candidate views must beat
  every control by at least 0.5%, with control max/min drift at most 1%.
  Recompute class-balanced rates from raw timestamps and check every output,
  incident64, draft proposal, acceptance count, reset and allocation identity.
- Read packet139 `evidence/device-smoke-A`: twelve prompts, 64 tokens each,
  every token exact, original oracle binding, matching binary/selection,
  device isolation, released lease and completed drain.
- Then run the fresh `build/device-cards01-a` chain. No second-lane grid.

`ready.json` stays false until both device prerequisites pass. To refresh it,
run `orchestrate.py --evidence-only`, then `verify_ready.py`. The latter refuses
missing, failed, changed or stale evidence. `ready.json` contains the complete
manual coordinator chain command. Preparation does not start it.

The sole new proposal is
[`../lane-queue/proposed-p139-smoke-A.txt`](../lane-queue/proposed-p139-smoke-A.txt).
It is planned in a disposable queue, never appended to a live queue. Expected
smoke duration is 240–360 seconds; its 1800-second watchdog exceeds four times
the upper estimate. The unit name is `screen-packet139-smoke-A.service`.
Host admission includes the 1,271,398,400-byte table and fixed buffers, for
105,424,393,216 required available bytes before loading both ranks.

CPU preparation entry points, from the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet139-orchestration/prepare139.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet139-orchestration/validate_cpu.py </dev/null
```

These are for a fresh, unlaunched copy only. They reuse verified packet137
binaries and numerical proofs; they do not compile or load a model. Native
launch-limit probes need unlimited virtual address space and consume only
metadata; capped CPU startup probes remain below 4 GiB. Runtime imports never
set resource caps. Root must retain 25 GB free and local builds stay below
300 MB. No power, memory, swap or page-cache settings are changed.

Every chain window probe runs the actual `chain_entry.main`, parser,
selection, environment and lane reservation code to intercepted native exec.
The real queue loop checks inputs, oracle completion, storage and malformed
receipt refusals. Smoke probes run the actual entry and worker under the
queue-generated environment and unit name, including real unit-property and
closed-environment validators. Only operating context, leases, predecessor
receipts and device execution are synthetic and confined to scratch.
The old environment refusal and old oracle/K2 failures remain negative controls.
The oneAPI library path is embedded; no temporary environment file is sourced.

After a qualifying chain, `prepare_submission.py --chain <chain> --output
<fresh-folder>` constructs the portable evidence bundle, result and promotion
attestation. `submission.py --help` exposes the complete submission CLI.
Preparation pins `scripts/packet49_record_threshold.json` and derives the
superseded record ID and rate from its last valid row. If bundle8 posts a
record first, that row becomes the comparison; otherwise the current record
remains. The ledger is checked again before writing the prepared submission.
Notes disclose the quantized compressed model, exact oracle, full BF16 KV,
unchanged target verifier and owner-authorized 128-token scope:
`realistic_final_gate.passed=false`. No public submission occurs in this task.

`native_startup139.py` also runs fifteen fresh startups using packet137's
hash-verified CPU mock binary and the new windows' actual parsed argv. This
covers both ranks and all three KD reference invocations, with banks and
`token_input=both` retained. Temporary plan paths are resolved to the exact
canonical input metadata and hashed. Numerical device addresses, weight
payload upload and readback remain mocked. Shared K0/K1/K2 proofs are reused
explicitly; their entry and queue paths still execute here. The native startup
receipt is required by readiness, alongside the intercepted device probes.
