# Packet115 boundaries

| Arm or method | Outcome | Revisit condition |
| --- | --- | --- |
| Per-kernel `SPV_INTEL_maximum_registers` | Still excluded; not used here | Separate compiler qualification |
| Module-wide LARGE for BMG-G31 | Installed compiler accepts it; expert image uses 256 GRFs | Requalify after compiler/IGC changes |
| E5 V8 with duplicated output epilogues | Three flag stores and six flag loads; fails zero-spill Gate 1 | Common epilogue is the qualified replacement; first source retained |
| Default/LARGE shared kernel names | Could merge SYCL identities or ELF symbols | Keep distinct image namespaces and separately linked artifacts |
| Direct queue submission during prepared capture | Would violate the existing runtime capture protocol | Retain packet103's prepared-submit overlay across the DSO boundary |
| CPU equality or zero-spill assembly as speed | Forbidden | Both fresh device micros, both orders and both controls, then v5 exactness |
| Single noisy route-pair veto | Not the registered speed gate with one pair/order/route | All routes remain measured; use registered matched-route medians |
| Broad startup composition sweep | Not needed | Check only production and the micro-selected candidate |

No quantization, KV format, FP32 reassociation or relaxed output comparison.
Do not launch a device job from these CPU preparation scripts. The coordinator
owns admission, fault watching, graceful teardown and both proposed jobs.
