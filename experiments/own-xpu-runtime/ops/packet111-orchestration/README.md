# Packet111 lean orchestration

CPU preparation only. No launcher runs automatically.

The fixed base is packet103 decision `1ad512f75aab3fce`. Only other-fusion and
the repaired target-head split can enter. A completed exact B grid must beat
both controls by at least 0.5%; a v5 bracket must beat all controls by at least
0.5% in both candidate views. A lane-A loss vetoes the dimension. Draft splitting
is excluded. Missing or failed evidence admits nothing.

Every composite screen must use the exact decision selection, binary, lane,
boot and oracle. Control / candidate / control runs are required independently
on A and B. Identical selections do not establish an improvement. The full
record chain remains blocked until its complete checks and device smoke pass.

The current decision is base/base: head gains 0.3697% on B, fusion 0.3176%.
Head's later A gain (0.5327%) does not replace the B threshold. Both composite
files pass temporary planning but execution refuses an identical candidate.
`ready.json` records the refusal. `device-entry.sh` is coordinator-only and does
not launch through preparation. The registered chain folder is fresh:
`stage2/packet111-record-bundle/build/device-cards01-a`.

Run CPU preparation with `nice -n 19 taskset -c 8-15,24-31 python3 -B
experiments/own-xpu-runtime/ops/packet111-orchestration/prepare.py </dev/null`.
The exec-limit proof is `launch_limit_gate.py`; its expendable CPU subprocesses
intercept both rank launches and prohibit device opens/native execution. Its
negative case alone sets an address-space cap. No device-imported module does.
`verify_ready.py` is read-only and intentionally exits with refusal today.

After a qualifying completed chain, `prepare_submission.py --chain <registered
chain>` creates the prepared payload/evidence. `submission.py` exposes the shared
submission CLI with the finalized strict validator. Neither runs automatically.
The validator copies the stage implementation with one schema correction:
packet111 inherits `packet103.window.v1` receipts. Packet identity, source hashes,
selection, exactness, admission, record-floor and prepared-payload replay checks
remain enforced. All four compositions pass synthetic receipt/payload replay;
those fixtures are tests, never measured evidence. The existing strict 512-token
flag remains false for the inherited 128-token chain and is not upgraded here.

`chain_adapter.py` checks the copied oracle helpers/manifest against the immutable
packet49 authority, and binds this orchestration code into the chain seal.
It preserves the four shipped screen seals. Runtime provenance is the shipped
source commit `83d5518ba` plus the hash-bound subsequent orchestration sources.
The live queues and all older packet/ops trees remain untouched.
