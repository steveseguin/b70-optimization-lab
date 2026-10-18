# Packet58w coordinator contract

Use the exact environment-embedded `chain_command` from `ready.json` only
after `verify_ready.py` passes. The service name is
`packet58-onecard-58w-b`; output is the fresh `evidence/card0-58w-b` directory.
The final orchestration marker binds the command hash and preparation commit.

Before launch, the coordinator pauses and drains lane B and keeps the
whole-host hold through all seven windows and 90-second gaps. It obtains a
fresh `evidence/fault-review-58w.json` with this packet's `fault_review.py`.
The review retains the frozen two-known-fault policy and newest captured
kernel timestamp minus two seconds. No review was captured during preparation.

K1a/K1b/KD run at nice19 on helper cores. W2m/WS/WS128x/WS128 run at nice0
on lane-A cores. Every model window uses tile16, overlap, target-only,
zero-copy misses, 18 GB immutable expert cache and context4096 BF16 KV.
K1 must qualify zero-copy twice; no streamed fallback is allowed for overlap.

Each stage starts once, drains gracefully and retains evidence. Failed
readiness, identity, admission, output or fault checks stop new launches.
No automatic retry, kill escalation or service restoration. Only WS128 is
a timing result; all windows are required for the later submission validator.
The strict 512-token gate stays false.
