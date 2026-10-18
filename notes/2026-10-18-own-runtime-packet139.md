# Packet139: bundle9 prepared ahead of the device verdict

Bundle9 is bundle8's banked rollback plus packet137 `token_input=both`.
This task prepared a new packet and orchestration copy. It did not launch a
model, service, queue job or chain. Packet136's running chain and every
existing packet tree were left alone.

The review26 rule is fixed before new bundle9 device data: use packet137's
lane-B v5 original/both/original/both/original bracket, require both candidate
views to beat every control by at least 0.5%, control max/min drift at most
1%, and every output exact. Add the new lane-A composed 12×64 smoke, checking
every token. Then admit the chain. No second-lane grid is required or queued.

## Copy and identity

- Initial main was `0524d881762487f533b5a47b95b5fb0069047d10`; pull/rebase
  refused unrelated dirty orchestration files. Fetch confirmed HEAD matched
  origin/main. Other authorized work advanced main during preparation.
- [New packet](../experiments/own-xpu-runtime/stage2/packet139-record-bundle/README.md)
  preserves all 184 packet137 symlinks, with literal target comparison against
  `find -type l`. The oracle is the original packet49 link, checked through
  `oracle-binding.json`, `shared_oracle.py` and its complete receipt.
- Native copies come from packet137 **v5** builds, not its stale root build.
  Both hashes, actual native source closure, table/target/state/full-shape
  proofs and exact selection are bound. No compilation or table copy occurred.
  The engine revision remains `981a673c8`; new Python wrapper sources have
  their own sealed identity.
- The sole bundle9 view keeps banks, the 80128-row prefix, unchanged target
  verification and full BF16 KV. Output authority remains
  `iq3-p49-split32-v1`. Host admission includes the table and fixed buffers.

## CPU checks and failures retained

[The CPU report](../experiments/own-xpu-runtime/ops/packet139-orchestration/cpu-final.json)
and [focused tests](../experiments/own-xpu-runtime/ops/packet139-orchestration/tests.log)
record the completed checks. All eleven windows run the real entry, closed
environment, parser, selection and startup assembly up to intercepted native
exec. The actual queue loop checks its real unit gate, input/oracle checks,
storage and malformed-window refusals. Only operational leases, predecessor
receipts and host/device activity are synthetic in disposable scratch.

Smoke planning uses the actual queue-generated
`screen-packet139-smoke-A.service` unit and embedded oneAPI library path.
Positive and negative native getrlimit checks are separate from capped CPU
mock tests. The old confirm environment failure remains a negative control.
The copied drain fix is tested. No runtime import imposes CPU resource caps.

The new CPU mock startup executes the real parser and production allocation
paths for fifteen new-chain invocations, including all three banked KD
reference startups. It uses the hash-verified existing packet137 fixture;
there is no rebuild, model payload read or GPU access. Legacy K0/K1/K2 proof
reuse is explicit. K2's numerical fixture cannot fit this task's 4-GiB cap;
its real entry argv and retained measurement-validator replay still run.

Preparation found and fixed a missing copied chain binding, the shared-oracle
source key, and a smoke output-root distinction. A concurrent preparation
edit invalidated an in-progress seal as intended. Native mock pilots caught
a retained `nice` prefix and an expired scratch plan path. Failure logs remain
in the new orchestration evidence; the final run follows resealing and uses
hashed canonical input metadata. None of these CPU failures touched a device.

## Device handoff and submission

[The proposed smoke](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p139-smoke-A.txt)
was planned on a temporary queue. Expected duration is 240–360 seconds, with
an 1800-second watchdog, exceeding four times the upper estimate. No live
queue changed. The fresh chain path is
`stage2/packet139-record-bundle/build/device-cards01-a`; it is absent.

[Readiness](../experiments/own-xpu-runtime/ops/packet139-orchestration/ready.json)
keeps device eligibility false while either prerequisite is missing. The
reader recomputes raw bracket rates and checks tokens, acceptance, proposals,
selection, binary, reset and allocation identity. It does not trust the
parent's stored speed verdict or require the parent's different threshold.

The complete submission tool pins the record ledger at prepare time and
reads its current last valid record ID and rate. If bundle8 posts a record,
that row is superseded; otherwise the existing record remains the comparison.
There is no hard-coded superseded ID in the notes. Prepared portable evidence,
attestation, CLI preflight and tamper refusals have CPU tests. Notes disclose
the quantized compressed model, unchanged verifier, full BF16 KV and the
owner-authorized 128-token scope with `realistic_final_gate.passed=false`.
No external submission was prepared from synthetic data or sent.

CPU work uses nice19, cores 8–15/24–31, Python `-B` and closed stdin. No sudo,
settings changes, reboot, driver action or process termination occurred.
Build copies total under 67 MB logically, below the 300-MB cap; the final
report records free root space above 25 GB and peak child memory below 4 GiB.
Large inherited source inputs have explicit retention and restoration notes.

The last workspace write is `READY-FOR-DEVICE.json`, after the preparation
commit is pushed. It names that commit and the smoke proposal SHA-256.
It marks CPU preparation complete, not permission to skip device readiness.

The staged whitespace check reports only retained patch context, copied parent
source whitespace and raw failure-log whitespace. Those evidence bytes are
preserved. No existing tracked file is included in this preparation commit.
