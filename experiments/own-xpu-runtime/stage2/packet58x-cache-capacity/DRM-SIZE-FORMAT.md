# Packet58xd DRM size format verification

The running host reports `Ubuntu 7.0.0-39.39~24.04.1-generic 7.0.14`.
`drm_print_memory_stats` calls `drm_fdinfo_print_size` for the total and other
memory fields. Its suffix table is exactly empty, ` KiB`, ` MiB`. Starting
with bytes, it divides by 1024 only while the size is nonzero and exactly
divisible, stopping after two divisions. Zero prints `0`; 1 GiB prints
`1024 MiB`. GiB is not a supported suffix. Unaligned values remain exact.

Verification used the matching Ubuntu binary package, without root, device
access or installation. Its extracted vmlinuz MD5
`f561cb5793e15151f11f690b9337ce38` matches the installed dpkg file manifest.
The matching modules package supplies System.map. At `ffffffff820e1d20`,
the formatter tests zero and the low ten bits, shifts by ten, checks again,
and selects the final MiB entry after a twenty-bit shift. The call from
`drm_print_memory_stats` at `ffffffff820e1e71` is retained in the disassembly.
The three string pointers resolve to an empty string, KiB and MiB.

- [Exact formatter and caller disassembly](evidence/kernel-7.0.0-39-drm-size.asm).
- [Exact suffix and format strings](evidence/kernel-7.0.0-39-drm-units.txt).
- [Upstream v7.0 source](https://github.com/torvalds/linux/blob/v7.0/drivers/gpu/drm/drm_file.c), checked against the exact binary rather than assumed identical.

Downloaded inputs, kept in temporary storage and never installed:

| Input | SHA-256 |
| --- | --- |
| [Signed kernel package](https://archive.ubuntu.com/ubuntu/pool/main/l/linux-signed-hwe-7.0/linux-image-7.0.0-39-generic_7.0.0-39.39~24.04.1_amd64.deb) | `9fce0856eee538bdd8521ad94946c2c7a3a7b82483cee7451a2275f9f2ab842a` |
| [Modules package](https://archive.ubuntu.com/ubuntu/pool/main/l/linux-hwe-7.0/linux-modules-7.0.0-39-generic_7.0.0-39.39~24.04.1_amd64.deb) | `65816a77c57fbc2c186c3d93ec7dd0b84d573fa3dc454734ea3c036db66ddcbf` |
| Extracted vmlinux | `4fcb06e6e829fd2d598fdfcb9bf54ff29af81a29d0f4fed0c65622bd037af9a4` |
| System.map | `1a62dc637ff18f5cfd620e3104e7787e56883e6654e14f0730076eb507480fe9` |

The parser accepts ASCII digits with no suffix, or one space followed by
KiB/MiB, allowing the fdinfo field's surrounding spaces/tabs. It rejects
signs, decimals, Unicode digits, unknown units, extra tokens and values whose
converted byte count exceeds uint64. The Python and actual C++ header run the
same boundary and malformed fixtures. Additional tests cover mixed units on
duplicate client FDs, multiple clients and the unchanged 30.5 GB reserve gate.

The packet-wide source audit found two additional consumers: the admission
receipt reader silently multiplied any numeric prefix by 1024, and the native
post-load guard required KiB. Both are repaired. Other active fdinfo readers
only inspect client/device identity; sysfs readers inspect topology or memory
block state, not DRM sizes. Archived provenance is preserved verbatim.

`rebuild_drm_entry.py` restores owned source inputs and rebuilds only the
device entry, reusing the unchanged owner/backend/kernel objects and host
executables. Its 2 GiB address-space cap applies to the compiler and linker.
The original build receipt is preserved in `lineage/58xc-build.json`.
The drain audit excludes the restored `frozen-inputs` historical build cache;
all active runtime files remain scanned. That cache contains the original
parent's old drain code, which is neither imported nor run by this packet.

After compiling, the helper removes only restored JSON metadata whose original
bytes are verified in the archive and which is absent from the current build
source closure. This prevents historical sibling pin maps from appearing as
current manifests. `restore()` recreates them for historical analysis or a
future build. Both initial temporary-plan refusals are retained under
`evidence/queue-plan-smoke-58xd-*-refusal.log`; final plans pass with the
unchanged coordinator guard.
