# Persistent rolling reset: controller refusal before first ROW

The first two-request qualification (`persistent-rolling-qualified-a`) stopped
after all four native owners completed initial RESET, before any target ROW.
All four owners exited with status 1 through the cooperative failure path. No
new GPU fault signatures were observed. This is a failed controller test, not a
passed model-state or speed result.

The controller used `any(stage.shared)` to check shared publication was cleared.
The socket fixture used `bytearray`, whose iteration produces integer values.
Real file-backed `mmap` iteration produces one-byte objects: even `b'\x00'` is
truthy. Consequently the correct all-zero mappings were rejected. Independent
inspection found all four 266,304-byte files entirely zero, each SHA256
`68c396a763508256bed83a144c693983e870386d6d56ac74ece114916a47b8eb`.
All native RESET receipts showed epoch 0→1, global sequence 1, zero frontiers
and unchanged allocation inventories. All native ROW traces were empty.

The correction inspects a bytes snapshot, `stage.shared[:]`, and must retain a
regression using actual file-backed mappings through the socket/reset path,
including rejection of a stale nonzero final byte. The native binary
`02a47c059444af0e9179612461a8078e4308f3357fb54e370421a2ba1b7788aa`
does not change. A corrected bounded run requires fresh plan/admission and
independent review; there is no automatic restart/retry.

The complete failed run and original Python sources are retained in the
605,892-byte archive `sc117-persistent-qualified-a-refusal-20261025.tar.gz`,
SHA256 `dff45f3fbb0c34606ea8c2df8be189d4015435296f5f41b31738f94149f41328`.
All 189 members were verified and the archive copied/rehashed on USB.
[Independent failure review](../experiments/own-xpu-runtime/research/continuation-2026-10-25/persistent-rolling-qualified-a-failure-review.json)
and [archive receipt](../experiments/own-xpu-runtime/research/continuation-2026-10-25/persistent-rolling-qualified-a-failure-archive.json)
retain exact identities. Originals remain in tmpfs.

The earlier 450-file source export remains a valid content/import receipt only;
its persistent controller contains this known bug and is not a qualified release.
The public 9d source download is unchanged.
