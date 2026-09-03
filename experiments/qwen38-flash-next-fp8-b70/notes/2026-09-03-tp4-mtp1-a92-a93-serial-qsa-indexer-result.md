# A92 / A93 result: the per-row QSA index path runs, and changes nothing

Date: 2026-09-03, 13:24--13:53 EDT

- A92 (overlay `2ebbf2a6`): the per-row path was reached during graph
  capture and stopped it: a small host-to-device tensor (`torch.tensor`)
  is not allowed while an XPU graph is being recorded ("wait method cannot
  be used for an event associated with a command graph"). Fixed by building
  the single-row query offsets on the device (`torch.arange`), overlay
  `69559951`.
- A93 (that head, `VLLM_XPU_QSA_SERIAL_SPEC_INDEXER=1`, otherwise the A85
  identity): the marker fired during capture, capture and the exact canary
  passed, and the battery reproduced A85 exactly: short
  `30.671318 / 31.292306 / 37.195940 tok/s` on the MTP0 hash, exact-2K
  `29a2947a...` (`7.56 / 8.35 tok/s`), exact-4K `bf25b9d1...` (`7.37 tok/s`);
  stopped after the first 4K row. Same-slot writes in the two-row index
  update are therefore not what moves the continuation; the index side
  path is cleared alongside the recurrent kernel (A85), the dense GEMMs
  and the MoE (offline gates) and graph replay (A83). The flag stays in the
  overlay, off by default.

What remains for the two-row verification step is located by trace, not
by hypothesis: A94/A95 capture every layer's output at the first forward
reaching position 2059 on the MTP0 and the exact-recurrent MTP1 lines and
compare row by row (`compare-q38-layer-traces.py`).
