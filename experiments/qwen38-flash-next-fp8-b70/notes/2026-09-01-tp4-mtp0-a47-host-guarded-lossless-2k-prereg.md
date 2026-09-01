# Qwen3.8 Flash-Next FP8 A47 host-guarded lossless-2K preregistration

Date: 2026-09-01
Status: frozen; deferred until the combined component finalist

A47 is the fresh attempt-47/port-19719 successor to the host-interrupted A46.
Its official checkpoint, source/runtime/kernel identities, TP4/EP4 MTP0,
2,304-token cap, synchronous PLE-only placement, public oneCCL, size-1
full-decode graph, compilation mode NONE, KV cache, prompts, exact 2K
authorities, quality battery, runtime verifier, and success interpretation are
unchanged.

Only bounded host-load controls differ:

- disk-backed swap is disabled while the supervised arm is alive, then
  restored on every ordinary exit;
- the runtime PCIe ASPM policy is set to `performance`, with both the AMD root
  port and Samsung endpoint required to report `ASPM Disabled`, then the
  original policy is restored;
- the supervisor records available memory, swap state, memory/I/O PSI, paging,
  NVMe block counters, AER counters, and a live kernel-journal stream every
  second;
- the arm fails closed below 32,000,000 KiB available memory, above 10% memory
  full-stall average, on any enabled swap, any ASPM drift, or the first new
  NVMe/root-port corrected event.

These controls change checkpoint-loading safety, not inference arithmetic or
performance selection. Static validation also proved that selecting
`performance` disables ASPM at both ends and that the original `default`
policy and 8 GiB swap are restored.

Frozen hashes:

- generated inner launcher: `8831ce6a9515002f3b23244c590169286aeeb34b5fee83005ee617c31dde3a50`;
- launcher: `03769e4dba7b3f9e75d01ced227a5f035a3ab5260564ca841d1fe1b6581474c7`;
- client: `fcdcb8d2d1982ff8914a8a0803187502dd8b2736ac452a2d3670e72668a6947e`;
- supervisor: `744c0dc1cda9370df71bd6ebbadd5242ec482871cbcaaae941cf194ccf57eb7a`;
- privileged host-control wrapper: `cf5c7ffa347663111cc66a818c7c5be28a72409c32bf64778dfc69b4767ec48d`;
- inherited A46 runtime verifier:
  `724528810e5316e1a32c013ecc6a2d0419f7063a7cedf6c5cb7d05d4ea672310`.

A47 is deliberately not launched immediately. The active optimization loop is
now component-first: qualify real-weight MoE, dense, quantization/cast, and
collective improvements without loading the full checkpoint, combine only
lossless winners, and use A47's guarded full-model path for the combined
finalist. This avoids paying one full load per small candidate.
