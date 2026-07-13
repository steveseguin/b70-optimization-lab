# Qwen27 Xe2 hot kernel module prototype

This experiment proves that a `bmg-g31` AOT SYCL kernel can live in a small
`dlopen` module, borrow the runtime's in-order `sycl::queue`, and consume
runtime-owned USM pointers without relinking the monolithic `ggml-sycl` device
image.

Run it with:

```bash
ZE_AFFINITY_MASK=3 ./build-and-run.sh
```

The proof operation is deliberately trivial. The useful artifact is the C ABI
in `q27_xe2_module.h`, including its no-work/fallback status contract. Q6 and
GDN modules use the same launch record and receive persistent, host-owned pack
descriptors. The module never owns, frees, or retains a queue, pack, state,
scratch, input, or output pointer.

The queue field is an opaque C pointer but intentionally has a strict
toolchain ABI tag: the module casts it to `sycl::queue *`. This is safe only
when host and module use the negotiated oneAPI/C++ ABI. A future Level Zero
native module could remove that restriction, but would be a different ABI and
is unnecessary for the first low-overhead integration.
