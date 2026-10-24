# Released attribution bundles archived

All six closed attribution state bundles were compressed and fully verified before
duplicate source removal, then copied to USB and verified again before local archive
release. 665,229,504 raw bytes occupy176,136,400 compressed bytes.
All phases passed. The fifteen independent micro fixtures and their exact hashes
remain intact; every original index, seal, state JSON and draft file is preserved.

[Explicit release](evidence/release.json) binds the successful real extraction,
independent fixture review and fixed header. The original executed reader and the
later unexecuted failure-flag correction stay separately preserved; archival uses
the independently checked successful copies, not a success boolean alone.

[Complete receipt](evidence/complete.json) binds these USB archives under
`/mnt/usb-models/own-xpu-runtime-results/`:

| Archive | Original relative bundle | SHA256 |
| --- | --- | --- |
| gsq-attribution-state-bundle-00.tar.gz | `rank0/state-2147483647/state.bundle` | `3edc38fdcfeeaf9863d029f53251004c3f980c425b664955ca355a6cec86e538` |
| gsq-attribution-state-bundle-01.tar.gz | `rank1/state-2147483647/state.bundle` | `92e2854c43a6f31bebe2ed507550517b9549e0fe864ea61172f0e21196aa7ade` |
| gsq-attribution-state-bundle-02.tar.gz | `warmup-none/rank0/state-2147483647/state.bundle` | `d368def6449d12d65f67a9fb2fdfacfe79c26dde48334ab1db7548f080cb7f2c` |
| gsq-attribution-state-bundle-03.tar.gz | `warmup-none/rank1/state-2147483647/state.bundle` | `945b3930e646c259e5d4cab7eec161cdac3bdfc95c52d5d073296be76e8be296` |
| gsq-attribution-state-bundle-04.tar.gz | `prompt-00-none/rank0/state-2147483647/state.bundle` | `755f367b82cb93ed7bca20108f30973048b489af04d1db029db68d768fe423cf` |
| gsq-attribution-state-bundle-05.tar.gz | `prompt-00-none/rank1/state-2147483647/state.bundle` | `8d0cc030e820a43baa7db01e61653107b2043e6e684cce3a1357b95f78e05072` |

NVMe restore metadata remains at
`/home/steve/own-xpu-runtime-results/gsq-attribution-bundle-archive-a/chunk-NN`.
Verify archive SHA, extract the single member into a fresh empty directory, and
check its size/hash against the original independently audited index. Restore only
to the missing path under the original `gsq-current-attribution-a` evidence root,
without overwriting any evidence. Retain its original index/seal/JSON and use the
qualified bundle reader for complete range verification.

The frozen path-limited parent and filesystem Job are unchanged. The128MiB quota,
27GB+64MiB NVMe floor and2GiB USB reserve remain. Archival ran after compilation,
with no GPU work. USB free space after completion is about8.92GB; any future run
must still pass its own live forecast and reserve checks. This is storage recovery,
not a speed result.
