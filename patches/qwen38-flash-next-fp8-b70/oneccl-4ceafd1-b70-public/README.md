# Public oneCCL `4ceafd1` B70 build (collective runtime of the certified lines)

The certified Flash-Next graph lines load this collective runtime through
`LD_LIBRARY_PATH` in front of the venv's own oneCCL:

| File | SHA-256 | Bytes |
| --- | --- | ---: |
| `lib/libccl.so.1.0` | `43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700` | 240,239,256 |
| `lib/ccl/kernels/kernels.spv` | `0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9` | (same bytes as the venv's `lib/ccl/kernels/kernels.spv`) |

Provenance (hybrid disclosure): built on 2026-07-11 from the unmodified
upstream `uxlfoundation/oneCCL` commit `4ceafd1` with oneAPI 2025.3 `icpx`,
`CMAKE_BUILD_TYPE=Release`, `COMPUTE_BACKEND=dpcpp`, `ENABLE_MPI=ON`,
`ENABLE_OFI_HMEM=ON`. The lab's later local oneCCL commits (size gate, event
chain) are **not** in this binary. A fresh rebuild is not claimed to be
byte-identical; the pinned bytes are the identity. The launch scripts verify
both hashes before serving (`ccl_sycl_allreduce_ll=twoshots` is selected at
launch through `CCL_*` environment, not by a code change).

Hosted copy: GitHub release `qwen38-flash-next-oneccl-4ceafd1-b70-public-20260906`,
asset `oneccl-4ceafd1-b70-public-lib.tar.zst` (15815628 bytes, SHA-256
`34dc2cad9603d6d910d677042cd6d992717f79b72e59add71dbdc302e65f8c24`); the decompressed tar is 245504000 bytes and unpacks to `lib/` with the
hashes in `lib.sha256`.
