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

The first comparator run builds a fingerprinted expanded-weight cache under
`/mnt/fast-ai/bench-results/qwen27-q6k-m6-top1/`. It is an external 1.26 GiB
initialization artifact and is never tracked by Git. Later runs mmap the
validated pack and avoid repacking the GGUF.

The C ABI is in `q27_xe2_module.h`, including its no-work/fallback status
contract. Q6 and GDN operations use the same launch record and receive
persistent, host-owned pack descriptors. The module never owns, frees, or
retains a queue, pack, state, scratch, input, or output pointer.

The queue field is an opaque C pointer but intentionally has a strict
toolchain ABI tag: the module casts it to `sycl::queue *`. This is safe only
when host and module use the negotiated oneAPI/C++ ABI. A future Level Zero
native module could remove that restriction, but would be a different ABI and
is unnecessary for the first low-overhead integration.
