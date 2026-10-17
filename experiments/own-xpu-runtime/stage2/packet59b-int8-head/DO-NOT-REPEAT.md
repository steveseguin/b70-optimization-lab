# Packet59b retained decisions

- Do not put the 234,329,088-byte extra head on rank1 under packet56's
  89,364,320-byte arena margin, raise the arena cap, or shrink target/KV/state.
- Do not replace any target-head rows with draft INT8 rows. The target needs
  its full head, including the prefix; its verification arithmetic stays fixed.
- Do not call the source head BF16-expanded: production uses signed Q6 codes
  plus FP32 group scales and metadata. A 50% traffic saving is unsupported.
- Do not attribute a screen difference solely to INT8: rank0 draft placement
  also changes scheduling and restores the parent's larger scratch reserve.
- Do not compare the changed draft logits against the old Q6 draft as a
  lossless gate. Check deterministic proposals and unchanged target output.
- Preserve packet56, packet59, packet58b, packet56w, packet60 and screen code.
- The lean seal is diagnostic only. A record still requires full device
  correctness, fresh-process determinism, representative performance and
  promotion evidence under the lane rules.
