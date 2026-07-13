# Qwen27 Xe2 hot kernel module prototype

This experiment proves that `bmg-g31` AOT SYCL kernels can live in a small
`dlopen` module, borrow the runtime's in-order `sycl::queue`, and consume
runtime-owned USM pointers without relinking the monolithic `ggml-sycl` device
image.

Run it with:

```bash
ZE_AFFINITY_MASK=3 ./build-and-run.sh
```

The module now also contains the production Q6_K x Q8_1 M=6 fused top-1
boundary. Compare it directly with the exported integrated `libggml-sycl`
implementation and the captured real DFlash fixture using:

```bash
ZE_AFFINITY_MASK=3 ./run-q6-comparator.sh
```

The module also retains the rejected Stage-A GDN QKV+z experiment. It shares
one Q8_1 activation production and submits the heterogeneous 10240- and
6144-wide Q4_0 DPAS projections in one command group. Reproduce its real
layer-0-weight comparison with:

```bash
ZE_AFFINITY_MASK=2 ./run-gdn-qkvz-comparator.sh
```

It is deliberately not a runtime candidate: after 20 warmup rounds, two
repeatable 100-iteration uncontended B70 runs measured about 94.2 us versus
103.0 us for the two active integrated symbols, only 1.09-1.10x. This misses
the required 1.30x microbenchmark gate and projects to about 0.42 ms saved
across all 48 GDN layers, below the 2 ms cycle gate. The code and pack cache
remain as negative-result evidence and as a comparator for
future larger fusion boundaries.

The first comparator run builds a fingerprinted expanded-weight cache under
`/mnt/fast-ai/bench-results/qwen27-q6k-m6-top1/`. It is an external 1.26 GiB
initialization artifact and is never tracked by Git. Later runs mmap the
validated pack and avoid repacking the GGUF.

The GDN comparator similarly stores its one-layer DPAS and production-oracle
packs in a validated 90 MiB external cache under
`/mnt/fast-ai/bench-results/qwen27-gdn-qkvz-m6/`.

The C ABI is in `q27_xe2_module.h`, including its no-work/fallback status
contract. Q6 and GDN operations use the same launch record and receive
persistent, host-owned pack descriptors. The module never owns, frees, or
retains a queue, pack, state, scratch, input, or output pointer.

The queue field is an opaque C pointer but intentionally has a strict
toolchain ABI tag: the module casts it to `sycl::queue *`. This is safe only
when host and module use the negotiated oneAPI/C++ ABI. A future Level Zero
native module could remove that restriction, but would be a different ABI and
is unnecessary for the first low-overhead integration.
