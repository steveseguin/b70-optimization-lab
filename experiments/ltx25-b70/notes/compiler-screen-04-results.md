# Native activation compiler screen04: exact GPU qualification

September 14, 2026. All nine completed clips match the original images, video
latents, audio latents and waveform byte-for-byte. Five clips used compiled
native block24, across boat seed42, marble seed17 and bird seed123. The other 47 blocks remain
original eager execution. This is a one-block correctness qualification, not a
speed promotion or a qualification of all 48 blocks.

Both native stage shapes passed eager/candidate and candidate/repeat equality:
video [1,64,4096] and [1,256,4096], audio [1,26,2048], all BF16 on XPU1. Five
compiled clips completed 55 gate invocations, plus two internal compiled
qualification repeats and two eager reference forwards. Two emitted wrappers each
retain 15 native RMS, six sigmoid and two tanh-GELU calls, independently counted
from generated Python. There were exactly two compiled graphs. The unchanged
state, route ownership, restoration and strict deterministic-mode gates passed.

Preserving all these native operations clears the observed block24 mismatch.
Because added opaque boundaries can change scheduling/fusion, this is not proof
that a particular activation was the original first differing operation. Prior
failed RMS-only and decomposed candidates remain preserved.

First eager preview took 92.212s including startup; first compiled preview took
45.109s including compilation and native eager/repeat gates. Four warm compiled
previews were 6.579,6.635,6.680,6.513s (median 6.607s). Restored boat previews were
6.490 and 6.495s; the early warm eager boat was 8.611s. With drift and a different
fixture mix, this screen does not demonstrate a speed win. The original
256x256 final,25 frames,24fps,BF16 weights,8+3 sampling steps and control encoder
remain unchanged. No generated output or prompt encoding cache was introduced.

PID 17769 remains at 127.0.0.1:8188 on packet05, with an empty queue after the
screen, clean kernel postflight, no FAULT latch and matching endpoint identity.
A single controlled application replacement loaded this source; the host boot
and power/swap/page-cache settings did not change. Last dispatch was restored;
the qualified compiled candidate remains available in the same process.

Runtime manifest45dc23a7c0a0a234412e31a36225716edf60bb16ad342d96fe12f65139bccbe5.
Clientv4 SHA dad494b6f9caea254a2984c2e0d8669d72a7ab108fcced827eadf1bb43160cde.
Evidence: data/compiler-screen-04/ and
 data/compiler-screen-04-native-activations-result.json; migration identity in
 data/native-activations-migration-05/. Exact external campaign, request, graph
and kernel evidence is under /mnt/fast-ai/bench-results/ltx25-baseline-20260913.
The unchanged retention policy removed only verified redundant raw captures and
kept the last three campaign previews; protected originals remain intact.

Next: paired restored/compiled/restored measurements on this same resident
process to resolve timing drift, then a reviewed multi-block route implementation.
The scaling audit records repeated guard work, singleton state and graph-directory
collisions. Preserve late-mutation and fault-halt guards while reducing diagnostic
overhead. Continuous coherent streaming and faster-than24fps remain incomplete.
