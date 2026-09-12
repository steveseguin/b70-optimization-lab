# A361-A363: the extension's exact serial GDN mode removes the verify-step tax losslessly

Stage v2 `runtime-gdn-roundstate-bbae3c5-b70` (served stage with `_xpu_C` rebuilt from kernel
commit `bbae3c5` on `e421889`), promoted MTP1 diag line (overlay `f1d5cd88`, step timing), exact-2K
rows, ports 19974-19976. Preregistration: `2026-09-12-a359-exact-multirow-gdn-kernel-prereg.md`
(amendment 2).

| arm | GDN verifier rows | M=2 verify step (ms, median / min) | exact-2K rows tok/s (cold, warm, warm) | hashes |
|---|---|---|---|---|
| A344 (served stage, control) | Python serial path | 42.66 | 24.9 / 37.3 / 37.4 | afffd211 x3 |
| A361 (stage v2, no-op proof) | Python serial path | 42.62 / 40.9 | 24.8 / 37.5 / 37.5 | afffd211 x3 |
| A362 (stage v2) | extension exact serial mode + completion barrier | **33.69 / 31.9** | 28.5 / **45.7 / 45.9** | afffd211 x3 |
| A363 (stage v2) | extension exact serial mode, no barrier | 33.75 / 31.9 | 28.6 / 45.9 / 45.9 | afffd211 x3 |

Server logs confirm the mode engaged on all four ranks
(`VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT reached`). All rows exit 0; no overlapping
drivers this time.

## Reading

- The rebuilt extension is a no-op for the promoted configuration (A361 = A344 in hash and time).
- The extension's exact mode runs the plain decode kernel once per verifier row inside the single
  spec op, with the state passing through the BF16 cache between rows exactly as the Python path
  does, so the outputs are bit-identical (kernel probe PASS; server hash held on every row), and
  the M=2 verify step drops from 42.7 to 33.7 ms: the whole 8.7 ms tax the A355-A358 series could
  not attribute to the Python path's kernels or glue is gone. The warm exact-2K decode rate goes
  from 37.5 to 45.8 tok/s (+22%).
- The completion barrier costs nothing measurable; it stays on for the certification packet (it
  exists to order the raw SYCL chain against the following graph replay).

## Next

A364: the certified A305 frozen-client packet on stage v2 with the mode's exports
(`2026-09-12-a364-native-exact-gdn-certification-prereg.md`). Then the fresh-server repeat and the
promotion attestation.
