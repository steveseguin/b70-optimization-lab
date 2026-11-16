# Engine host memory (2026-11-16, helper agent's read-only findings, transcribed)

The engine holds ~6.2-6.9 GB anonymous host memory, flat after load (pr6 / tlx1 x200k smaps).

- Verified: the binary has 15 kernel images, 249.8 MiB (177.5 MiB kernel code, 55.3 MiB SPIR-V, 14.3 MiB .ze_info),
  2,751 kernels (`zebin_sizes.py`).
- Verified (byte-exact with glibc mmap rounding): each 401,972 kB per-card mapping = 3 copies of image 9 (130,262,840 B)
  + 1 copy of its SPIR-V; each 196,440 kB mapping = 3 copies of image 10 (67,048,616 B); smaller mappings of card 0
  = 3 copies of images 0, 1, 5, 7, 12. They appear during `get_kernel_bundle` for the six contexts
  (backend_sycl_v41.hpp:688): host anon 693 -> 6,891 MiB inside the 2.9 s "kernels built" window, before the upload.
- Inferred: per context 3 copies of every image + 1 of its SPIR-V = 804.7 MiB per card, 4.71 GiB for six (likely one
  in the SYCL / Unified Runtime program, two in the Level Zero module). Every MiB of kernel image costs ~18 MiB of host
  RAM (3 copies x 6 cards), every MiB of SPIR-V 6 more.
- Ours: `h_engm` (mt.inc:545) 144 MiB with OWN_PX_BIG, never read with eng_dev on (the default); `rwbuf` (hpp:1433)
  2 x 8 MiB per card; `h_engrm` 25 MiB in use; `h_ckv` / `h_ik` reserve not resident in TP mode; upload staging 408 MiB
  freed after the upload; `build_rope_tables` (hpp:6010) four 24.9 MB vectors built even with the rope window, then
  freed (raises glibc's mmap threshold to ~25 MB: later allocations under it go to [heap]). ~1 GiB of [heap] not
  identified (close to 6 x 177.5 MiB: perhaps one more code-sized buffer per context, or freed blocks).

Exact (bit-identical) savings, best first:
1. `-exclude_ir` in the ocloc options (`-Xsycl-target-backend=intel_gpu_bmg_g31 "-exclude_ir -options ..."`): ~221 MiB
   per card (~1.3 GiB) + 55 MiB off the binary. Check with `python3 -I zebin_sizes.py OLD NEW` (every kernel's code
   identical). Not yet checked that ocloc takes the flag through this path.
2. Compile out kernels production never launches (count launches first): each MiB of image ~18 MiB of RAM.
3. `malloc_trim(0)` once after load (unknown, up to ~1 GiB). `GLIBC_TUNABLES=glibc.malloc.mmap_threshold=1048576` once
   to see the heap's pieces in smaps.
4. `madvise(MADV_PAGEOUT)` the runtime's copies after the first step (to swap, contents kept; a page-in stall risk).
5. `h_engm` only when !eng_dev: 144 MiB. 6. one `rwbuf` per card: 48-96 MiB. 7. rope vectors only without the window.
