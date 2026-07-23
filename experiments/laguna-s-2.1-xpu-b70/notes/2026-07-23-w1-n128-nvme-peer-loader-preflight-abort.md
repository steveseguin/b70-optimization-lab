# W1 N128 NVMe recovery: peer loader preflight abort

The third local-NVMe recovery root is closed as an infrastructure-only abort:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T135330Z
```

It ran on clean boot `0b7f98a5-e50a-46a5-81ea-15938b55317a`, kernel
`7.0.0-28-generic`, with taint `0`. The gate verified all 118 local model
files, `xpu-smi` version and four-card discovery, the exact PCI/DRM mapping,
and strict four-card idleness. The hash-pinned oneAPI runtime correction then
worked: `sycl-ls` exited zero and enumerated all four B70s as
`[level_zero:gpu][level_zero:0]` through `:3`.

The next command was the standalone oneAPI 2026 peer-read binary. The pinned
loader path had been scoped to `sycl-ls`, so the binary's process loader exited
127 before `main` or any peer kernel could execute:

```text
error while loading shared libraries: libsycl.so.9: cannot open shared object file
```

The gate failed closed before either XCCL pass, either N64 gate, N128, a model
service, or model generation. Kernel delta contained only `-- No entries --`;
the Xe reject file was empty and kernel taint remained zero.

The evidence manifest verifies completely. Stable hashes are:

```text
evidence.sha256          98cd4147482b66f521d7c5c6624fafa7e434f4b2f39a8bb84d4ab24c916fbfff
final-status.txt         78298030805065cd6e15e1a2f55995edc83222f9ed40ae71286716064db9d0f0
sycl-ls-verbose.log      9d3d8bafd881f9e1c16f66042efadd17c97d020d9d5d1fc5b08592100a154719
peer-read.log            3c4baa231fa5b7034dfb2061c9ea4174e08a17eef4d96a7bfd472b46e0b3f60d
kernel-delta.txt         19c4e28b2f54ea8f217db4e622b0a5c758efa7b77ce2dc0394b6d159568c0b2e
kernel-reject-events.txt e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

Read-only `ldd` proves that the existing pinned oneAPI path resolves
`libsycl.so.9` and every other peer-binary dependency. The correction applies
that same path to the peer command and explicitly unsets the already-invalid
ambient `UR_LOG_LOADER` value there. The Python/Torch commands retain their
frozen virtual-environment runtime resolution.

The new recovery root is registered as:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T140038Z
```

This retry is an infrastructure correction on the same clean boot, not a
performance-conditioned restart. A1 remains the first model generation after
a complete recovery pass.
