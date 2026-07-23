# W1 N128 post-reboot recovery: ntfs3 preflight abort

The first post-reboot recovery root is closed as an infrastructure-only abort:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-postreboot-recovery-20260723T120411Z
```

The gate started at `2026-07-23T12:57:26Z` and exited `124` at
`2026-07-23T12:57:43Z`. Both bounded `xpu-smi -v` and
`xpu-smi discovery -j` completed, and the exact four-card PCI/DRM mapping
passed. The next operation, the strict idle proof, wrote only the header and
the device-0 self row before `timeout 15 xpu-smi ps` expired.

This was not an Xe device timeout. At `2026-07-23T08:57:28-04:00`, PID 14951
(`xpu-smi`) triggered:

```text
kernel BUG at fs/iomap/buffered-io.c:1061
iomap_write_end
iomap_write_iter
iomap_file_buffered_write
ntfs_file_write_iter
vfs_write
ksys_write
```

The evidence root was being written directly to `/dev/sda2`, mounted at
`/media/steve/CorsairExternal` with the in-kernel `ntfs3` driver. The Oops
therefore occurred in the redirected stdout write path. The process emitted
one row and then failed to finish the evidence-file write. The Xe-specific
reject file remained empty.

The root was sealed fail-closed. `sha256sum -c evidence.sha256` verifies every
listed artifact. Stable top-level hashes are:

```text
evidence.sha256  4fe2e1bef509c8118d65747e8909217e5532f2d314178b5814d0020fa96b30c8
final-status.txt 1ba5ecf998ef6c010dcf080f7bd955834ea32f8802a8010e4101d89f75d8de71
kernel-delta.txt 4fa49d66407eef5fdccf2cad4e878cb9716ed2435c688e5ef81c7129f8cfc2d9
```

No SYCL peer test, XCCL pass, N64 oracle, N64 production-fixture liveness call,
N128 candidate, model service, or model generation ran. The corresponding
downstream artifacts are absent.

The kernel is now tainted `640` by an Oops and warning. This boot is rejected
for benchmarking even though the fault was outside Xe. Do not reuse the failed
root and do not issue another GPU probe in this boot.

Required next action:

1. preserve this root and the additive structured incident manifest;
2. reboot the host;
3. stop the auto-started Gemma and display services;
4. place all live recovery and endpoint output on a Linux-native filesystem,
   never directly on the `ntfs3` mount;
5. preregister a distinct recovery-evidence root;
6. repeat the no-generation hardware/runtime gates; and
7. keep recovery A1 as the first post-recovery model generation.

This restart is conditioned only on a preflight filesystem/kernel failure. No
throughput, output-quality, candidate, or benchmark observation exists.
