# Upstream, kernel and driver review for the two-B70 host (2026-10-03)

Written after a 12-day gap (last GPU work 2026-09-21). Two sources: a web review of releases and
issue trackers, and a read-only Codex review of the local upstream clones (`~/src/vllm-current-main`,
`~/src/vllm-xpu-kernels-current-main`, `~/src/llm-scaler-reference`, all fetched today). Anything
marked *unverified* was not confirmed at a primary source.

## The "kernel 7 fixed it" tip does not apply as stated

This host ran `7.0.0-31-generic` for every September fault (first boot on -31: 2026-09-14). The
useful question is which 7.0 build, not whether to be on 7.

| Kernel | Where | What changed for `xe` |
|---|---|---|
| 7.0.0-31 | installed, baseline | all five copy-engine faults of 09-15..09-21 happened here |
| 7.0.0-34 | noble-updates 09-22 | security only, no `xe`/DRM/AMD changes |
| 7.0.0-38 | noble-updates 10-01 | exec-queue teardown deadlock fix ("guc: Hold device ref until queue teardown completes"), "Return error on non-migratable faults requiring devmem", PTE index fix for chunked binds, NULL deref in `xe_pt_zap_ptes_entry`, dma-buf reference for imported BOs, an AMD IOMMU locking fix |
| 7.0.0-39 | noble-proposed 10-01 | "Order ring writes before ring tail updates" (closed an upstream BMG report of bcs timeouts during eviction), "Don't hand out the flat CCS storage as usable VRAM", "Wait on external BO kernel fences in exec IOCTL" |
| 6.17.0-35/41 | noble HWE (older) | no new fixes; two community reports of far fewer faults than 7.0.0-30 (one confounded by a fresh boot) |
| 7.2.x mainline | kernel.org / mainline PPA | one dual-B70 report of failing sooner than 7.0.0-31 |

Order chosen: -38 first (it is the supported build), then -39, then 6.17 as an A/B, one change per
boot, each judged by `scripts/fp8-start-cycle-soak.sh` (faults per service start, ten starts).

## Our fault signature is a known open upstream bug

`intel/compute-runtime#948` ("Sporadic permanent GPU wedge on dual Arc Pro B70 ... bcs
-ENOENT/-EINVAL") matches ours: copy-engine page faults, `Fault response: Unsuccessful -EINVAL`,
CAT errors, timed-out jobs. Open, no Intel fix. Reporters saw it on 7.0.0-27/30/31 and 7.2.3,
with compute-runtime 26.05 to 26.35 and GuC 70.58/70.65/70.72.1; none of those cured it. Two
practical notes from that thread: `docker rm -f` on a busy instance logs the same fault lines by
itself, and our own 2026-09-21 log shows a watchdog kill of a busy MiniMax run producing a bcs CAT
error in the same second. Related: `drm/xe#8390` (open), `compute-runtime#998` (B70
`malloc_device` fails above 19.3 GB).

## Firmware and user-space driver

- GuC: this host loads 70.54.0, which is what the 7.0 driver asks for. Upstream linux-firmware
  carries 70.72.1 (2026-08-05). Evidence that a newer GuC helps is mixed. Not changed today.
- `linux-firmware` package: an update is pending (`0ubuntu3.1`); which GuC it ships is
  *unverified*. Held back by the unattended-upgrades blocklist so it cannot change under a kernel test.
- compute-runtime: installed 26.22.38646.7 (PPA has nothing newer for noble on this host's
  sources). Upstream 26.35.39758.10 (2026-09-17) lists no BMG stability fixes, and a B580 `zeInit`
  abort was reported against .11 the day of this review. Not changed.

## vLLM, XPU kernels, llm-scaler (Codex review of the local clones)

Our lane is a patched v0.29.0-based image plus a fork of `vllm-xpu-kernels` (Aug 17). Upstream
`vllm` is 2,057 commits ahead (tags to v0.31.0), `vllm-xpu-kernels` 47 commits ahead (v0.1.15).
A v0.29 to v0.31 rebase is **high risk for bit-exactness** (Torch 2.14, Triton changes, default XPU
graphs, worker and quantization refactors), so it is not worth doing for stability alone.

| Hash | Date | Repo | Change | Verdict |
|---|---|---|---|---|
| `43abdd5` / `7230dfea50` | 09-02 / 09-29 | kernels / vLLM | preserve non-contiguous strides when pinning CPU tensors for UVA | PORT candidate (memory correctness) |
| `1dc2680` | 09-28 | kernels | guard empty FP8 group-quantization input (SIGFPE) | PORT candidate (smallest) |
| `da16a55` | 09-16 | kernels | fix ragged speculative GDN token traversal | PORT candidate, reconcile with our MTP overlays |
| `622934e61f` | 09-16 | vLLM | honor explicit worker `device_ids` | PORT if we use explicit placement |
| `6c18a54648` | 08-28 | vLLM | avoid unpinned host-to-device copies, touches model-loader utilities | WATCH: the only change near our weight-load fault window |
| `2a61f060d3` | 08-31 | vLLM | unquantized linear weights forced contiguous | WATCH |
| `ffe3bb3c72` / `e4340e41c9` | 09-02 / 09-22 | vLLM | XPU batch-invariant linear/matmul | WATCH, reconcile with our exactness patches |
| `17c93a1` / `bdfb02674f` | 09-13 / 10-02 | kernels / vLLM | reassociated block-FP8 scaling, B70 W8A8 GEMM tuning | WATCH: arithmetic change, ours is W8A16 |
| `d5051abaf1` | 09-25 | vLLM | prefix-cache hits with MTP | WATCH (published recipe has caching off) |
| `2ac6a6f` / `fb5171f` | 09-07 / 09-16 | llm-scaler | concurrent GDN state races, speculative rollback | WATCH (different GDN implementation) |
| `8b63154` | 09-24 | llm-scaler | FP8 GEMV/GEMM tail overreads and alignment | WATCH |
| `5802a41`, `79468c20ef`, `14f98cbe5d`, `ede4320`, `1fa01ff` | | | already in our image, or paths we do not run | SKIP |

"PORT candidate" means worth a diff review and an exact-output check, not a verified fix. Nothing
upstream claims to fix xe userptr invalidation, cross-device weight copies or copy-engine faults.
Codex could not inspect some upstream patches (missing objects in the clones) and did not test any.

Suggested order when the FP8 lane is next opened: the empty-input guard, then the UVA pinning pair
together with a read of `6c18a54648`, then the ragged GDN traversal against the MTP overlays.
