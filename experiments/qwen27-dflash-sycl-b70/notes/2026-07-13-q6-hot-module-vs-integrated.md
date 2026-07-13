# Q6 M=6 hot module versus integrated kernel

Date: 2026-07-13

## Outcome

The production Q6_K x Q8_1 M=6 fused top-1 boundary has been transplanted
into the versioned Xe2 hot module without changing protected llama.cpp. The
module passes the real native-DFlash production fixture and has no measurable
dispatch or device-time penalty relative to the current integrated AOT
implementation.

Three independent nine-iteration repeats on uncontended B70 GPU 2 produced:

| Repeat | Integrated wall median | Module wall median | Module/integrated | Host dispatch delta |
|---:|---:|---:|---:|---:|
| 1 | 2334.099 us | 2321.956 us | 0.994798 | -1.202 us |
| 2 | 2332.095 us | 2321.695 us | 0.995540 | -0.421 us |
| 3 | 2334.299 us | 2321.515 us | 0.994523 | -0.771 us |

An earlier supporting set on GPU 3, where an idle llama-server remained
resident, measured integrated `2333.188-2334.891 us` and module
`2321.506-2322.808 us` with the same exact IDs. The uncontended GPU 2 set above
is the headline result.

The small apparent module win is not promoted as a kernel speedup. The device
code is the same three-stage quantize/dot/reduce boundary; the likely
difference is that the module receives fixed-address scratch while the
integrated function enters the ggml pool allocator. The important result is
that `dlopen`/function-table dispatch adds no observable tax.

## Actual integrated comparator

The comparator does not compare against a second copied baseline. It links the
current protected AOT library and directly calls its exported C++ symbol:

```text
ggml_sycl_mul_mat_q6_k_xe2_m6_top1(
    ggml_backend_sycl_context &, const void *, size_t,
    const float *, int32_t *, int, int, sycl::queue *)
```

`nm -D -C` confirmed the symbol at `0x02da2c0` in
`build-sycl-b70-qwen36-mtp/bin/libggml-sycl.so.0.16.0`. The comparator mirrors
the exact compile-time context layout flags used by that library, constructs
the same `ggml_backend_sycl_context`, and gives integrated and module launches
the same in-order queue, device pack, and captured activation rows.

The protected llama.cpp source was read only. The other Q6 agent's dirty
microbenchmark and launcher files were not changed or staged.

## Correctness and fallback

All three repeats returned the five captured production and sampled IDs
exactly:

```text
[12305, 198, 727, 369, 36951]
```

The fixture identity remains
`data/qwen27-q6k-m6-top1-real-fixture-20260713.json`, SHA-256
`e2bcd65300f9fa4d7b733dd0491d3c01cf566aadbbf4e22f7587079867484e3f`.

An all-zero activation oracle forced a finite full-vocabulary tie. Both the
integrated kernel and module returned token ID 0 for all five rows, preserving
the lowest-ID tie rule through workgroup and global reductions. An invalid
pack-layout probe returned `Q27_XE2_BAD_LAYOUT` before enqueue, demonstrating
that the ordinary implementation remains a safe fallback for an identity
mismatch.

The module validates before submission:

- op, exact M=5 useful rows, N=248320, and K/stride=5120;
- in-order borrowed queue;
- one target-LM-head pack;
- exact expanded-pack bytes (`1,360,793,600`);
- Q6 layout version and Qwen model content tag;
- fixed-address scratch of at least `337,600` bytes.

After validation it enqueues the production quantize, dot/local-top1, and
global-top1 kernels. A submit exception returns `SUBMIT_STATE_UNKNOWN`, which
is deliberately not fallback-safe.

## Build and initialization economics

Touching the real Q6 module source and rebuilding its `bmg-g31` AOT `.so` took
`3.50 s`. The observed monolithic `ggml-sycl` link took `497 s`, so the real
kernel lane is `142x` faster to iterate—not merely the earlier smoke kernel.

The comparator also turns the expanded pack into a durable, fingerprinted
initialization artifact:

- external path:
  `/mnt/fast-ai/bench-results/qwen27-q6k-m6-top1/qwen36-27b-output-q6k-expanded-v1.pack`;
- bytes: `1,360,793,664` including its 64-byte identity header;
- SHA-256:
  `d1d9eb5d71a9d5249d548732d8070371d62cfa839d4a2b3eeaab2d44f845a98f`;
- first CPU expansion plus atomic write: `1.515740 s`;
- warm validation/mmap: `27-34 us`;
- host-mapped pack to B70 copy: `352-361 ms`.

The realized artifact also exposed and corrects an arithmetic error in the
earlier independent safety audit: the payload is `1,360,793,600` bytes, not
`1,355,847,680`. The live formula and module check are
`K*N + (K/16)*N + (K/256)*N*2`; the prior note's representation and combined
residency totals have been corrected accordingly.

The device copy is initialization-only. In the eventual runtime the existing
persistent device pack is handed directly to the module, so neither disk I/O
nor the 353 ms copy belongs in a decode cycle. The cache does make standalone
kernel experiments restart rapidly and records enough identity to reject a
wrong model/layout rather than trusting file size alone.

## Classification and next action

Classification: **pass**. This is an iteration-speed and integration-safety
milestone, not an end-to-end decode record, so it is not a LocalMaxxing
submission.

The next hot-module candidate should use a larger fusion boundary where
fixed-address scratch and one module rebuild can produce a real cycle win.
The first candidate is the audited M=6 GDN joint Q4_0 QKV+Z boundary with one
activation quantization and one submission; it must beat the current separate
integrated boundary and preserve exact outputs before any runtime integration.
