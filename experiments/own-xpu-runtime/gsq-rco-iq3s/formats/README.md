# GSQ scalar formats — CPU qualification

This additive adapter implements original scalar Q2_0, Q4_K, Q5_K and IQ4_XS field equations and a deterministic BF16-input row GEMV. Existing own-runtime types delegate to the original scalar decoder. No frozen loader, runtime or native kernel is changed.

The test-only reference extracts unchanged dequantization and half conversion function bodies from the pinned local ggml source (MIT license), with the exact block definitions and normative IQ4 nonlinear levels. The extracted source stays in the ignored attempt directory and is never an inference dependency. IQ4_XS equations also reuse the earlier original packet8/packet10 format work. [Source pins](source-pins.json) record the upstream commit and exact files; [the adapter](formats.hpp) contains our implementation.

The fixture compares every FP32 decoded bit, every indexed element, and an independently traversed ordered row GEMV. It tests each packed field bit against a nonzero baseline and requires the reference output to change; patterned three-block rows exercise all index/group boundaries with positive/negative scales, signed zero, subnormals and maximum finite half scales. All 63,488 finite half encodings are checked. NaN payload/sign parity and native arithmetic are explicitly outside this finite-scale proof. The row GEMV tree defines this CPU path and does not establish parity with every selected device kernel.

Twelve real rows (first, middle and last row of one representative tensor per type) are selected from the frozen census. Exactly 14,220 model bytes are read, with offset/extent, inode/device/size/timestamp identity checks and per-slice SHA256. No full model hash or model execution occurs. Test inputs/outputs must be complete disjoint buffers; this is a scalar interface, not an allocation ownership API.

Run once after source review:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 taskset -c 8-15,24-31 nice -n 19 python3 -B experiments/own-xpu-runtime/gsq-rco-iq3s/formats/build_cpu.py --run-cpu
```

The helper snapshots sources before generation, acquires the shared compiler turn, enforces a 4 GiB address-space limit and 27,000,000,000-byte root floor with a 50 MiB write reservation, and gives compilation and execution separate 120-second deadlines. Failed attempts stay under ignored `build/`; tracked evidence records all source, dependency, compiler and sampled-input identities. No service, device, model, download or host-setting action is provided.

The first bounded run passed: **6,780 cases / ordered GEMV rows, 2,863,488 FP32 values, 63,488 finite half encodings, seven refusal checks and all twelve real rows**. Own and reference aggregate output SHA256 are both `3c4263023d181a8be0f0c23c04a74edb972a0c33e4845e4433e61c6046437be7`. The [CPU receipt](evidence/cpu-proof.json) binds compiler, both translation-unit dependency closures, sources and sampled-row identities. The exact generated reference, objects, binary and logs remain in the ignored attempt directory recorded there; raw model slices are never tracked. Total current packet disk use is below 2 MiB. No failed compile or arithmetic attempt occurred. This does not admit the GSQ model into the Engine: quantized expert/dense dispatch, BF16 primitive gains, F16 PLE convolution, placement/cache sizing and MTP remain separate integration gates.
