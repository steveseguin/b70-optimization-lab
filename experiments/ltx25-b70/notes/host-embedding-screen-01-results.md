# Host embedding screen: ten exact clips, OOM during return to control

2026-09-14. The encoder candidate completed five full clips with all four raw
outputs byte-identical to the original BF16 references. The initial control
also completed five exact clips. Every candidate receipt proves the original
CPU BF16 token table, actual int64 XPU2 IDs `[1,1024]`, final F32 XPU2 embeddings
`[1,1024,3840]`, full remaining encoder parameter/buffer residency, and native
loaded-size accounting. All original sampling steps, 256x256 final output,
25 frames/24 fps, and original decoder/transformer were retained. No prompt or
output caching was used.

The15-request campaign failed before its final control arm could complete.
At18:12:58 UTC Linux's global OOM killer killed serverPID116013; exec15201 exited137.
Xe GPU0 reported a bcs engine reset/fault at18:13:01, after the process kill.
ClientPID116455/exec91667 exited1. Its original profile subprocess reported a
WebSocket disconnection; the subsequent `/proc/116013/fdinfo` snapshot error
masked that exception at the client top level. Both errors remain recorded.
No automatic application restart, driver reset, reboot, swap/cache/power change
or device probe followed. ROOT/FAULT.json latches the incident. Passive18:14:41
postflight finds both processes absent and all four render devices unowned;
that does not establish recovered device health or permit another native run.

Saved generation03 retirement metadata establishes that the encoder was fully
restored to CPU and its separate table registration retired before the process
died. Source then calls `unload_all_models()` while retaining the whole component
tuple; this can materialize the video-model shards in CPU RAM before releasing
old owners. That ordering creates a concrete RAM-peak hazard. The exact native
instruction at the OOM is not captured. The next source-only change keeps the
video model, shards, VAEs and upscaler resident and replaces only the encoder,
with explicit owner-release and available-memory gates. Packet11 stays unchanged
as failed evidence; recovery and new native admission remain separate gates.

Performance is incomplete screening evidence only. Excluding each initial load,
the first-control preview median was6.46244s; host-table median6.35094s. Four
matched positions favored host-table, median−109.03ms preview and−61.51ms encoder.
Boat repetitions are not independent fixtures, and the missing final control
prevents the registered bracketing comparison. There is no performance promotion,
continuous-streaming qualification, or claim that the subsecond goal is met.

[Incomplete timing](../data/host-embedding-screen-01-incomplete-timing.json),
[terminal export summary](../data/host-embedding-screen-01/summary.json),
[incident postflight](../data/host-embedding-screen-01-incident/postflight.json),
[kernel evidence](../data/host-embedding-screen-01-incident/kernel.log), and
[client output](../data/host-embedding-screen-01-client.log) preserve the outcome.
The text-only export revalidated the10 completed requests' original comparisons,
identity, metadata and retention receipts; it contains340 text files at archive
SHA256`ddb49954cf20a562386197d0e394e97e6fa0b4d8088f0efc5b3c7ecfe78ad4b6`.
No raw equality was rerun after failure. Ten already-verified raw archives and
seven older previews were pruned during the campaign; the latest three previews
remain. Reference raw archives remain protected. Incident logs and both failed
transition receipts are also preserved separately outside the compressed export.
