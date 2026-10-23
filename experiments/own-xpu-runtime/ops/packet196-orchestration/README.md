# Packet196 orchestration

Private additive derivation from packet58c23chain-orchestration; shared tooling unchanged. Final READY is withheld until `finalize.py` passes source/binary bindings, raw screen admission, script-mode argv, native parser, seven-window rehearsals, submission tests and pin guard. `DERIVATION-READY.json` alone never authorizes a launch.

The manual launcher requires inactive endpoints, PAUSE-B held, PAUSE-A manually archived, no live lane/device owner, fresh output, exact sealed command, fresh fault review, memory/storage floors and valid final READY. It never stops services, touches latches, retries or resets a device.

Preparation is complete only when the mirrored final READY and `verify_ready.py` pass. The proposal remains `entry-proposal.jsonl`; nothing was appended to the live queue. The screen binary is reused without compilation. Read-only verification:

```bash
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/ops/packet196-orchestration/verify_ready.py
```

`launch_chain.sh --dry-run` performs CPU checks and explicitly defers the privileged device-holder inventory. An actual manually coordinated launch requires the pinned metadata-only helper, complete root descriptor visibility, absent STOP-A/B incident latches, and successful systemctl discovery. No retry or endpoint lifecycle is implemented here.
