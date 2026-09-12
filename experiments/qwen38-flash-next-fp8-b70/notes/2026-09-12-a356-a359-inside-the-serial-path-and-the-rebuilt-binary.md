# A356-A359: the serial-path tax is not its kernels, and the rebuilt binary reproduces the line

MTP1 promoted line, exact-2K rows, step timing. Preregistrations:
`2026-09-12-a356-a358-inside-the-serial-gdn-path-prereg.md`,
`2026-09-12-a359-exact-multirow-gdn-kernel-prereg.md`.

| arm | change | M=2 verify step (ms) | rows |
|---|---|---|---|
| A344 control | promoted line | 42.66 | afffd211 x3 |
| A355 | views fast path | 41.80 | afffd211 x3 |
| A356 | Python serial path OFF (stock multi-row spec kernel) | **33.91** | 8b4f5fcb x3 |
| A357 | serial path, per-row decode kernel launches skipped | 42.97 | 1acd0833 x3 |
| A358 | serial path, state copies skipped | no result (see below) | |
| A359 | rebuilt `_xpu_C` (stage `runtime-gdn-roundstate-3279856-b70`), flag off | 42.61 | afffd211 x3 |

## Reading

- The serial path costs ~8.7 ms per verify step and buys the exact hash (A356). Its two per-row
  decode-kernel launches per layer cost nothing measurable (A357: skipping them leaves the step at
  43.0). Combined with A355 (the index/copy glue was 0.9 ms), the serial function's own work is
  not where the time goes; what remains inside it is the state copies between spec columns
  (A358, not measured yet) and, outside it, whatever the runner does differently when the
  serial selector is on. The direct test is A360: the stock multi-row kernel made exact.
- A359 is the no-op proof for the rebuilt extension: the same hash on every row and the same
  step time as the promoted control. The rebuild used the served build's cache values (MOE off,
  GDN on, SYCL 2025.3 pinned, Release, isolated dependency sources); its `_xpu_C` additionally
  links `libmqa_logits_kernels_xe_2.so` (present in the stage), the only NEEDED difference.

## Incidents (both mine)

- A358 was stopped by the supervisor's host-memory guard (MemAvailable fell to 11.8 GB, floor 12 GB)
  because the kernel rebuild's compilers ran during its warmup. Rule recorded: no builds while an
  arm is starting.
- A359 needed four launches: the generator emitted the stage option as a launcher export, then its
  build-head substitution also rewrote the padding-receipt check, then leftover cache directories
  from the failed launches made the launcher refuse. Each failed launch had already spawned its
  timing driver, and those drivers were still polling port 19972 when the fourth launch became
  healthy, so the three exact-2K rows were requested by more than one driver at once (the row
  harness of the losing driver reports "File exists", rc=2). Hashes are per request and held; the
  tokens=2 median agrees with A344, but A359's timing should be treated as approximate and the
  arm repeated cleanly when the lane reopens. When the server was stopped with those requests in
  flight the xe driver logged two compute-engine resets (01:40:29 local, cards 23 and 27), and the
  frozen launcher refuses to launch for six hours after any such event: A360 is blocked until
  about 11:41 UTC. Rule recorded: after a failed launch, stop its driver by pid before relaunching.
