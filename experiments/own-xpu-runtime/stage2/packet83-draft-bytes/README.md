# Packet83: fewer draft-head bytes

Four views share one packet75-derived binary: production, separate Q4/g32
head prefix, 99.0% text-coverage prefix, and 98.5% text-coverage prefix.
The target head, target arithmetic, verifier, controller, BF16 KV, 24/24 split
and rank-1 draft placement are unchanged. Q4 changes proposal arithmetic only.

- [Census](CENSUS.md): raw packet77 hit attribution and byte projections.
- [Preregistration](PREREGISTRATION.md) and [coverage selection](coverage.json):
  fixed independent text chooses 80,128 and 74,752 rows; no suite-tuned N.
- [CPU closeout](CPU-PREPARATION-CLOSEOUT.md): exact scope and remaining gates.
- [Coordinator jobs](WINDOW.md): either lane runs a full grid; the other confirms
  its exact improving winner between fresh controls.
- [Retention](RETENTION.md): sources and receipts are retained; build products
  are local research artifacts, not a published standalone recipe.

Q4/g32 stores signed four-bit codes plus FP32 scales every 32 values. It adds
146,227,200 bytes (139.45 MiB) on rank 1, derived at startup from the existing
identity-checked Unsloth Q6_K GGUF head. It is not an original-BF16 quantization.
The full target head keeps its original bytes. Prefix-only arms share that head
and allocate no extra weights. The MTP block is unchanged.

CPU preparation runs no GPU or service. Serial compilation creates GNU-host and
Intel-device binaries; the device binary is never executed during preparation.
Both compilers convert and calculate all 91,392 real prefix rows twice in fresh
CPU processes, with identical quantized bytes and outputs. Every head output
matches an independent scalar reduction reference. Eight complete production-size
startup mocks exercise allocation, capture and selection consumers; mock payloads
replace model uploads, not allocation/startup logic. Miniature native-controller
runs compare target bytes with packet75 and repeat every draft twice.

The actual GPU oracle, acceptance and performance remain pending. The roughly
1.62% Q4 hit-cycle saving is a bandwidth projection before acceptance changes.
Text coverage cannot predict Q4 argmax changes. Screens are diagnostic 128-token
runs and do not meet the 512-token final promotion gate.

Only these packet entry points are current: `build_engine.py`, `full_shape.py`,
`real_head_gate.py`, `cpu_gate.py`, `target_identity.py`, `python_gate.py`, `seal.py`,
`final_check.py`, `queue_plan.py`, `run_screens.py`. Other copied helpers retain
packet75 implementation history; they are not a registered packet83 chain.
All CPU commands use nice19, CPUs8–15/24–31, python3 -B, OMP_NUM_THREADS=2,
stdin /dev/null, at most8GiB address space and one compiler at a time.
