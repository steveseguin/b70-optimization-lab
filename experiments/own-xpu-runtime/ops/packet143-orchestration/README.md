# Packet143 orchestration

CPU preparation only; no work queued or launched. The packet README explains evidence, selection and commands. `ready.json` is the device-chain decision; `READY-FOR-DEVICE.json` is the final preparation handoff, not permission to skip that decision. The all-enabled smoke proposal is an unqueued preparation example.

Use nice19, taskset8-15,24-31, python3 -B and /dev/null stdin for CPU commands. `prepare_runtime.py` verifies CPU seals; `--seal` is an explicit regeneration action. `verify_ready.py --refresh` selects from pinned component evidence and requires the exact selected lane-A smoke and >=2% product. `device-entry.sh` is manual and refuses false readiness. No service is restored afterward.
