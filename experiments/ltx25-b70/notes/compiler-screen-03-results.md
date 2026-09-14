# Native RMS compiler GPU screen03

September 14, 2026. The candidate failed exactness and is not promoted. Native
RMS preservation reduced the first block's differing audio bytes from 5,923 to 10;
video remains 54 differing bytes with exactly the same expected/actual hashes
as screen02. Both native eager reference hashes match screen02. This implicates
RMS decomposition in much of the observed audio difference, but does not prove
which individual site first diverged or identify the remaining source.

One native stage1 wrapper compiled successfully and contains 15 opaque native
RMS calls, independently counted in emitted Python. No native compiled repeat,
second stage, full compiled clip or candidate speed is qualified. The first
native block quality gate failed before those steps. All outputs were finite
and metadata matched. Differing-byte counts are not unequal-value counts or
error magnitudes.

The two unchanged eager clips matched all four original raw references. First
preview took 105.669560536s including initialization; the warm preview took
7.953629607s. Do not compare this single slower control to prior 6.262s as proof
of a model regression without matching startup/resource history. No source
change beyond compiler backend/imports and identity pins was deployed.

PID 6502 exited after one controlled SIGINT; the replacement LTX application is
PID 12199 at 127.0.0.1:8188. The host boot did not change. Startup checks passed;
postflight recorded an empty queue, zero kernel-fault matches and no FAULT latch.
The numerical failure latch remains set. Preserve the process and failed
receipts; do not retry the same gate or reset it in place.

Packet04 manifest: c4e0f7e56fc7bbc51101894d79d279dd9886f07272868dc99cc7953c647a65c9.
Client v3 SHA:cbc83f1ca7618ae40a7956d105731e155162332457b0d9a4b9493fbb14ff1af6.
Backend SHA:09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb.
Original 25 frames, 256x256 final, 24 fps, BF16 weights, 8+3 steps and control encoder
remain fixed. Verified redundant raw archives were deleted by the unchanged
bounded retention policy; protected originals remain intact.

Evidence: data/compiler-screen-03/, data/compiler-screen-03-native-rms-result.json,
data/native-rms-migration-04/, scripts/export-compiler-screen-03.py. Full external
root: /mnt/fast-ai/bench-results/ltx25-baseline-20260913; campaign compiler-screen-03,
server encoder-server-compiler-04. Source deltas and initial CPU gates remain in
the native-rms-runtime-04 and native-rms-backend-cpu packets.

Next: localize remaining rounding differences, starting with emitted sigmoid,
GELU and residual operations. Preserve original kernels when capturing intermediate
values; an instrumented recompilation can alter fusion. The conditional plan is
native-rms-next-localization.md. No numerical tolerance will replace byte equality.
