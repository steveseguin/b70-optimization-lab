# Packet 122 continuation contract

Parent: sealed packet 121, manifest
`8f1d4e3b5b8ca79f79a43b9a6f0acec252e58fdde72b92ffb5ea0743f71444dd`.
The [121 contract](../20261010-continuation121-stream/CONTRACT.md) remains binding
except for the namespace and explicit reservation option below. This is CPU
preparation, not a new GPU qualification or a speed claim.

Packet id 122; prefix `stream122-`; comparison `stream-candidate-122-v1`;
qualification clip base 12200000, stream base 12201000. All 176 numerical
identities and 3,168 qualification graphs (after namespace normalization) remain
identical to 121. Native samplers, upsampler, conditioning, decoder arithmetic,
precision, seed and operation order are unchanged. Replaced parent files are
preserved under `provenance/packet121`; all ancestors are recursively verified.

Frames remain 49/97/121/145. **169 stays disabled for both display arms** in the
contract, launcher, builder geometry and client. The refined receipt census does
not clear 0.5 GiB for the near-floor dual walk plus a 0.25 GiB safety band on every
card. Moving display cannot repair sampler-card pressure. The
[145 results and refined census](../../notes/2026-10-10-continuation121-results-145.md)
separate sampled physical-free minima from allocator peaks and unmeasured kernel
peaks. Floors remain 8/8/2/9 GiB before requests/conditioning, with inherited
post-stage/decode rules; no snapshot or safety walk is removed.

The optional xpu:2 decoder replica still requires frame/cone/eager-display at
121 or 145 frames. Its default transient reservation stays 4 GiB at 121 and
5.640625 GiB (6,056,574,976 bytes) at 145, inherited from 121. The old 4 GiB
reservation is inadequate for the conservative 145 estimate. The new optional
`LTX_DISPLAY_REPLICA_TRANSIENT_GIB` accepts an explicit reservation at least the
length default and at most 8 GiB, representing a whole number of bytes. It is
refused for xpu:3 display, invalid lengths, nonfinite, fractional-byte or smaller
values. It changes an application admission budget, not any host memory setting.

Before copying require physical free >= actual resident bytes + selected reserve
+ 2 GiB; before decode require reserve + 2 GiB; afterward require 2 GiB. Observed
peak allocation or reservation growth may not exceed the selected reserve.
An explicit selection is stored as `display_replica_transient_budget_bytes` in
server options, frozen status and receipts; omitted means the sealed length
census. Qualification, live evidence and client expectations check the selected
value. Explicit client expectations are required for an explicit server value.

The replica has no encoder or graph pool. All nine qualification chunks retain
full-image equality against uncached eager xpu:3; the eager/graph/repeat chains
must match all latent, image, waveform and anchor bytes. Every live cone chunk
retains display-last-frame equality. Shared latches remain binding. No 121-frame
verdict qualifies 145, and packet 121's live qualification does not automatically
qualify packet 122. The first eager geometry must match the sealed formulas.

145-frame dg1/cap1/eager-display/xpu:2 is the coordinator's next diagnostic. It
is not declared memory-safe: recurring retained reservations on xpu:3 in the
121-frame replica run can consume the projected margin. A refused gate remains
a refusal; there is no automatic retry or fallback. Raising the xpu:2 reserve
cannot relieve xpu:3. Seam/audio quality and fresh-run native identity still need
review. The sink's frame removal and audio behavior remain inherited.

Use `/home/steve/.venvs/ltx25-baseline/bin/python -B`, OMP/MKL at most 4.
`run_tests_122.py` blocks render-device opens, process signals and live sockets,
and guards Python children. Launchers are checked with `bash -n` only during
CPU preparation. [Launch reference](LAUNCH.md) and
[build receipt](../../data/resume-20261008/continuation122-build.json) hold the seal
and exact validation counts. No GPU work, live preflight, launch, endpoint,
unit, signal, existing-run write or host-setting operation is part of this build.
