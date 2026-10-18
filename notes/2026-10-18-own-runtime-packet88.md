# Packet88: corrected-half and rollback attribution

Closed with attribution; no new lossless mechanism justified a build.
Rollback already overlaps drafting. The corrected token changes the embedding,
lookups and downstream layer inputs, so the wrong guess's layer results cannot
be reused. The remaining measured setup is small; enqueue time overlaps device
work and cannot be counted as a serial saving.

Packet77's raw receipts reproduce C = 12.655226 ms and R = 0.569390 ms for
252 misses in the first 1,188 intervals. Every redo copies 19,025,640 bytes;
29,601,792 spare-bank bytes are already omitted under the existing overwrite
proof. The restore kernel has no saved device timer. Its time is unknown,
not zero and not the entire rollback command's 0.569390 ms.

[MISS.md](../experiments/own-xpu-runtime/stage2/packet88-miss-path/MISS.md)
contains the host/device accounting, sampled classes, input-dependence analysis,
copy-byte split and mechanism decisions.
[Recomputation](../experiments/own-xpu-runtime/stage2/packet88-miss-path/attribute.py)
passes against the raw receipts and records source hashes in
[attribution.json](../experiments/own-xpu-runtime/stage2/packet88-miss-path/attribution.json).
[Closeout](../experiments/own-xpu-runtime/stage2/packet88-miss-path/CLOSEOUT.md)
records the missing measurements and the proof needed to reopen this lever.

The brief explicitly permits closing with attribution. Consequently no runtime
candidate, byte/state/full-shape gate result, executable, seal, screen job or
proposed queue file is claimed. Depth two, draft relocation and draft bytes
were not reopened. Packet84 was read as the prospective source parent; every
existing packet tree, shared v4 file and ops file was left untouched.

Preparation was CPU only on steve-b70s, under nice19 and cores 8–15,24–31,
Python `-B`, stdin `/dev/null`, with a 4 GiB address-space ceiling. No compile,
model load, GPU, service, sudo, host-setting change, reboot or process kill ran.
Root had 15 GB free at entry; this packet remains below 1 MiB.

The requested opening `git pull --rebase` refused the pre-existing dirty
packet70/75 ops and packet80 evidence files. `git fetch origin main` showed
HEAD and origin/main identical (0 ahead / 0 behind); no stash or edit of those
files was used. The attribution and closeout are committed directly on main
and pushed together. Only this packet, this note and the CURRENT pointer belong
to this work.
