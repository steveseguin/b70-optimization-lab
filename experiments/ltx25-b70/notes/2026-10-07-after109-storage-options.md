# Storage after the109 resource pilot

Read-only metadata audit; no raw tensor payload hashing, cleanup, process checks,
compression, GPU access or endpoint calls were performed by this audit.
109 completed its29-request three-fixture49-frame pilot and remains protected.
A full ten-fixture plan needs9 GiB runtime writes plus384 MiB source preparation
above the unchanged50 GiB floor. Observed free bytes were56,621,461,504
(about52.73 GiB); fresh admission is still required.

A straightforward existing-artifact option is sufficient. The old97
`two-way-w2-b4-p1-dxpu2-r2` timed600 arm has587 emitted ordinary nlink1 archives.
All587 stored per-tensor shape/dtype/finite/hash maps match their protected
batch4 references; all587 original parity reports record exact four-tensor
comparison with the correct reference/candidate execution pair. Retain its
first ten `f97-twowayw2b4p1dxpu2r2-timed-13` through `-22` and all
`stability-01-b4-*` references. The remaining577 archive paths (`timed-23`
through `-599`) total11,655,794,688 allocated bytes, about10.85 GiB.

If fresh whole-file equality and the original exact comparator validate this
fixed set, retirement would leave54.213 GiB after the full9 GiB runtime and
384 MiB source allowances—about4.21 GiB beyond the reserve. This neither relies
on retiring live109 outputs nor changes the new qualification verifier. Exact
paths, stats and stored metadata hashes are in
`data/resume-20261007/after109-storage-options.json`; they are screening evidence,
not a deletion plan. The narrow new helper is under
`recovery/20261007-after109-b4-retirement/`, with coordinator-owned plan/apply.

The October6/7 ledgers show package caches and eight cold staging trees were
already consolidated. The Qwen cache/staging archives are the preservation
copies and should stay. The additional external research backup passed full
readback and was unmounted, but the USB device's long-term reliability remains
unqualified; it should not become the sole home of unique research. Internal
/home, /mnt/fast-ai and /tmp share the same ext4 capacity. tmpfs is not durable
storage and is not an acceptable escape from the reserve during this GPU work.

Lossless compression of inactive archives could preserve whole bytes, but the
F32 safetensor header cannot establish a compression ratio. A bounded trial
would need output space, decompression/hash verification and a durable restore
ledger before retiring originals; no payload compression or ratio measurement
was attempted. Since an exact-duplicate arm already supplies sufficient room,
compression is unnecessary for this next full suite.

Sequentially comparing and retiring new duplicate outputs against ten immutable
native keepers could reduce peak disk use, but requires a new capture ownership
and verifier protocol, durable per-request maps, crash/failure handling and
truthful post-retirement proof semantics. It also moves storage work into the
measurement protocol. Preserve this as a future design option, not a prerequisite
or a silent change to this qualification. Existing deterministic duplicate
retirement is the smaller, independently reviewable step here. No reserve
reduction, unique-experiment deletion, reference-chain rewrite or automatic
cache eviction is proposed.
