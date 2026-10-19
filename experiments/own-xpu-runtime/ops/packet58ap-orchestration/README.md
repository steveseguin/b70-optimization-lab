# Packet58ap handoff

CPU preparation only. The final `READY-FOR-DEVICE.json` is written after all
proofs and seals. `ready_for_device` remains false until the current packet58am
v5 output exists, matches the vendored candidate and passes the explicit rule.
Do not edit a saved readiness boolean to release it.

The coordinator runs the packet's `seal.py --verify` and
`verify_ready.py --output ready.json`, then follows its `WINDOW.md`.
The generic `onecard-chain.sh packet58ap-onecard-chain packet58ap-orchestration --check`
is a passive packaging check, not device authorization. Its live path repeats
readiness, fault review and command-digest checks.

`entry-proposal.jsonl` is solely a shared CPU rehearsal input, never a queue
entry. `entry-report.json` is the actual `ops/rehearse_entry.py --report`
result. The independent native sequence proves the unranked CPU preparation
path that the shared adapter cannot express.

The bootstrap scripts record how the private copy was made. They are not
launch scripts and must not be rerun over a sealed packet. Restore binaries
using the packet's `restore_build.py` and vendored archive instead.
