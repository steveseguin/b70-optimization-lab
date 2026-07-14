# GDN QKVZAB production integration - unverified handoff

Date: 2026-07-13

## Status

The protected llama.cpp tree contains a default-off production integration of
the cleared M=6 GDN QKV/Z/alpha/beta/folded-alpha-gate hot kernel. The complete
source patch compiles in the JIT build, and the core kernel also passed BMG G31
AOT device compilation and linking. No server was launched and no real decode
graph, output parity, acceptance, cycle timing, or strict-suite result was
measured. Treat the integration as **unverified**.

The scoped snapshot is
`patches/qwen27-gdn-qkvzab-m6-unverified-20260713.patch` (SHA-256
`a1243599baf105d7faca1582707a2173d519a8947e15a550c205dfed31fca7f0`).
It was generated against the protected dirty source state, not clean upstream.
Do not apply it without first restoring the prerequisite Q4 M=6 pack/runtime
work recorded in this lane.

## Evidence that exists

The standalone hot-module result is valid and remains the reason to preserve
this lane:

- four ordinary projections: `143.309-143.440 us`;
- QKVZAB joint projection: `99.407-99.457 us`, or `2.105-2.114 ms` saved over
  48 recurrent layers;
- ordinary projection plus full alpha gate chain: `147.737-147.768 us`;
- folded candidate: `99.237-99.247 us`, or `2.328-2.329 ms` saved over 48
  layers;
- Q4 outputs exact; alpha maximum absolute error `1e-5`, beta `4e-6`, and
  folded gate `2e-6`.

This is standalone module evidence only. It does not prove that the production
graph matcher claims the intended tensors or preserves end-to-end speculative
acceptance.

## Implemented guarded contract

The patch adds:

- `GGML_SYCL_XE2_GDN_QKVZAB`, default off;
- `GGML_SYCL_XE2_GDN_QKVZAB_LAYER_LIMIT`, default `0`;
- `GGML_SYCL_XE2_GDN_QKVZAB_MIN_FREE_MB`, default `2048`;
- CPU creation of BMG Q4 ABI-v2 mirrors for exact
  `blk.N.attn_qkv.weight [5120,10240]` and
  `blk.N.attn_gate.weight [5120,6144]` tensors;
- a pre-allocation free-memory check and a post-pack free-headroom log for each
  packed tensor;
- an exact BMG G31, graph-off, M=6 matcher that requires QKV, Z, F32 alpha,
  F32 beta, `dt`, and `a` to share the expected graph identity and input;
- pack pointer/layout/byte checks, device-buffer checks, fixed names and
  shapes, and graph-order checks;
- skip activation only after the fused submission returns success;
- exclusion of a claimed GDN node from the older raw-gate fusion, avoiding a
  double claim while allowing ordinary fallback if dispatch fails.

The patch also adds a one-shot, default-off fixture hook selected by
`GGML_SYCL_CAPTURE_GDN_OUT_M6_DIR` and
`GGML_SYCL_CAPTURE_GDN_OUT_M6_LAYER`. It only matches the ordinary, unfused-add
Q5_K `ssm_out.weight [6144,5120]` M=6 path and is designed to write:

- `input.f32`: row-major `6 x 6144`;
- `projection.f32`: ordinary pre-add `6 x 5120`;
- `residual.f32`: `6 x 5120`;
- `add.f32`: ordinary post-add `6 x 5120`;
- `runtime.txt`: layer, tensor names/types/dimensions, and output strides.

The requested fixture directory is
`/mnt/fast-ai/bench-results/qwen27-q5k-gdn-out-m6/capture-v1/`. It was not
created or populated. A reopening run must add `manifest.json` with magic
`Q27Q5GDNM6FIXTURE`, model fingerprint, exact GGUF payload offset and bytes,
runtime/build/environment identity, file sizes and hashes, capture labels,
reorder state, and strides.

## Build evidence

The full snapshot compiled successfully with:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp-jit \
  --target llama-server -j 6
```

This built `ggml-sycl.cpp`, `mmvq.cpp`, linked `libggml-sycl`, and linked
`llama-server` after the fixture hook was added.

The core QKVZAB integration, before the final fixture-hook/headroom-log edit,
also completed BMG G31 AOT device compilation and linking with:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31 \
  --target ggml-sycl -j 8
```

No runtime result follows from either build.

## Memory economics

The QKVZAB mirror cost is exact:

| Component | Per layer | All 48 |
|---|---:|---:|
| QKV Q4 ABI-v2 pack | 29,491,200 B | 1,415,577,600 B |
| Z Q4 ABI-v2 pack | 17,694,720 B | 849,346,560 B |
| Combined | 47,185,920 B (45 MiB) | 2,264,924,160 B (2.109375 GiB) |

Using the `2.328 ms` hot-module saving, this lane offers about
`1.104 ms/GiB`. The Q5_K GDN-output candidate uses `33,914,880 B` per layer,
or exactly `1.515625 GiB` for 48 layers, and its measured opportunity is above
`4 ms`, at least `2.64 ms/GiB`. Q5_K therefore has more than twice the memory
efficiency and must be tested first.

The last strict full187 plus Q6 server had about `3.84 GiB` free. Installing
both all-layer packs would consume `3.625 GiB`, leaving only about `0.215 GiB`
before other runtime variation. That is not acceptable headroom. Do not scale
QKVZAB to all 48 layers before the Q5 result. Reopen with partial limits and
record the real free-memory curve; likely checkpoints are `1`, `8`, `16`, and
`24` layers.

## Reopening gate

Reopen only when GPU runtime work is authorized again. The next sequence is:

1. Rebuild the latest snapshot in BMG AOT.
2. With MMVQ-add fusion disabled, capture the real Q5_K fixture above and
   complete its manifest.
3. Run QKVZAB at layer limit `1`; prove matcher/dispatch counts, Q4 exactness,
   alpha/beta/gate tolerances, emitted token IDs, and speculative acceptance.
4. Measure pack/headroom checkpoints at limits `1/8/16/24`. Stop before the Q5
   pack budget is threatened.
5. Scale only if the measured cycle saving remains economic. Promotion still
   requires at least `2 ms` cycle reduction or a `>=3%` paired short crossover,
   followed by the fixed cold realistic suite with all cache counts zero.

Until those gates pass, do not enable the feature by default and do not submit
any LocalMaxxing result from this work.
