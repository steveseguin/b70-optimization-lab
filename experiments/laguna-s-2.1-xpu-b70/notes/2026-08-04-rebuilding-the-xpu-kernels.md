# Rebuilding the XPU kernels: two constraints that stop the first attempt

Date: 2026-08-04 America/Toronto

Status: **measured while attempting the TP-sharding change. Both are
prerequisites for any kernel work on this stack and neither is documented
elsewhere in the campaign.**

## 1. Build with the 2025.3 toolchain, not 2026.0

`libtorch_xpu.so` links **`libsycl.so.8`**, which ships with oneAPI **2025.3**.
The 2026.0 compiler produces `libsycl.so.9`, and a kernel package built against
it cannot load alongside this torch.

```
ldd .../torch/lib/libtorch_xpu.so | grep libsycl   ->  libsycl.so.8
/opt/intel/oneapi/compiler/2025.3/lib/libsycl.so.8   present
```

Both compilers are installed, and `2026.0` appears in the runner's
`native_library_path`, so picking the wrong one is easy. Set:

```bash
CMPLR_ROOT=/opt/intel/oneapi/compiler/2025.3
CC=$CMPLR_ROOT/bin/icx
CXX=$CMPLR_ROOT/bin/icpx
PATH=$CMPLR_ROOT/bin:$PATH
```

This is the toolchain question that came up earlier in the campaign and was
initially answered the wrong way round; one `ldd` settles it.

## 2. Build with `MAX_JOBS=1`

`csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.cpp` needs about **69 GiB of
compiler memory** in a single translation unit:

```
Out of memory: Killed process (clang) total-vm:77410160kB, anon-rss:69280708kB
```

On a 125 GiB host that fits **only if nothing else is compiling**. The default
parallelism kills the build at roughly target 754 of 1396.

`CMAKE_BUILD_PARALLEL_LEVEL` does **not** work: `setup.py` computes its own job
count (`compute_num_jobs`, line 98) and passes `-j=15` regardless. The knob it
honours is `MAX_JOBS`:

```bash
MAX_JOBS=1 python setup.py build_ext --inplace
```

Its heuristic at line 122 is `max(1, min(cpu_jobs, mem_jobs))`, so it does try to
budget memory -- but no per-job estimate survives one unit wanting 69 GiB.

Note the reboot removed `/swap24.img` (it was not in `/etc/fstab`), leaving 8 GiB
of swap. Restore it if headroom is needed.

## Copying a kernel tree

Copying the tree to experiment without touching the pinned one works, and the
runner supports it via `REPRO_KERNEL_TREE`, but three inherited
`CMakeCache.txt` files hold absolute paths to the original:

```
build/temp/CMakeCache.txt
.deps/onednn-subbuild/CMakeCache.txt
.deps/cutlass-sycl-subbuild/CMakeCache.txt
```

Delete those and any `CMakeFiles/` directories; keep `.deps/*-src` so the
fetched sources are not re-downloaded. The `.so` outputs are gitignored, so a
rebuilt copy still passes the runner's clean-worktree check.

`ccache` is configured as the compiler launcher and carries roughly half the
objects across from the original tree, which makes a re-run far cheaper than the
first pass.

## Why this matters

The work the warm trace argues for -- TP-sharding the experts to cut ~70.8 MB of
per-step all2all to ~3.54 MB -- requires exactly one code change plus a rebuild
([`2026-08-04-FINAL-the-ep4-partition-is-compiled-in.md`](2026-08-04-FINAL-the-ep4-partition-is-compiled-in.md)).
Without these two constraints the rebuild fails twice for reasons unrelated to
the change, which is enough to make the work look harder than it is.

## Boundaries

Both figures are measured: the `ldd` output and the kernel OOM message. No
serving measurement is affected; the rebuild happens in a copy
(`laguna-xpu-kernels-tpshard-20260804`) and the pinned kernel tree is untouched.
The protected `125.4619731637751 tok/s` conventional short-decode record is
untouched.
