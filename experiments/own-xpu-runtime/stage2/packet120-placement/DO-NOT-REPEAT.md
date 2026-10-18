# Packet120 boundaries

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md): placement admitted
on CPU; device equality, residency and speed remain pending.

- Only placement changes: target layer24, from rank1 to rank0. Both views use
  the exact same packet118 bundle7 selection and fixed 80,128 draft prefix.
- No v5 switch: allocation and topology change, so use fresh v4 processes.
- No CPU arithmetic pass is a real-model output or speed result. Device output
  must match iq3-p49-split32-v1 for every token of all twelve prompts.
- No rank0 expert offload was necessary. E1 half-cache is device storage.
- No inferred driver residency from arena bytes. Keep raw per-client DRM
  counters, allocator bytes and unmeasured global free VRAM distinct.
- Do not treat the full 2.3 ms outside-command time as target-race slack. The
  shared race slack is about 0.52 ms on packet108's source line. Measure misses.
- W0p is a pre-engine mini canary, so its split25 argument is allowed only on
  that canary path. Real split25 requires rank1 draft and context4096; no 32K.
- Both controls matter: >=+0.5% on B before A, then >=+0.5% on A. Exact outputs
  and identical per-prompt draft acceptance are independent requirements.
- Keep all existing packets, shared screens and live queues unchanged. Source
  changes during a CPU proof invalidate it; rerun after source edits finish.
- No Python import may install a resource cap in a device launcher. Both rank
  exec boundaries require unlimited address space and unchanged limits.
