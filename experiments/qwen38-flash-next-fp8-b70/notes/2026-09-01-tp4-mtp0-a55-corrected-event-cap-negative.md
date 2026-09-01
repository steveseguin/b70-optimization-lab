# Qwen3.8 Flash-Next FP8 A55 corrected-event-cap negative

Date: 2026-09-01
Status: bounded hardware-guard negative; diagnostic rows only, no promotion

A55 validated the revised 8-GiB local-read allowance but stopped at the
unchanged local-NVMe corrected-event safeguard. All four ranks loaded the exact
131-shard external checkpoint in `579.64` to `580.08` seconds at
`31.57 GiB/card`. KV sizing produced 3,456 tokens, full decode graph capture
completed in 51 seconds, the endpoint became healthy, and recovery passed.

The frozen quality battery reached its inherited accepted boundary: six of
seven exact semantic cases passed, with only the known code-execution case
failing; 16/16 repeatability, the long-context case, and cache-zero checks
passed. All three short rows returned the protected output hash
`5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0`
at `19.420733`, `18.546442`, and `19.071017 tok/s`, for a diagnostic median of
`19.071017 tok/s`. That is 7.006% below A44's retained `20.507849 tok/s`
diagnostic full-graph median, so the isolated `twoshots` collective gain does
not advance as a serving-speed candidate.

The first exact-2K row completed normally at `11.354325 tok/s` after TTFT. The
second row was stopped after 85/128 streamed tokens when the local Samsung NVMe
corrected-event counter reached 65 above A55's baseline, one beyond the frozen
64-event limit. The supervisor terminated the owned endpoint and restored swap.
The final `client rc=2` and incomplete second-row hash are consequences of that
deliberate stop.

Other gates remained healthy:

- minimum `MemAvailable` was `26,310,300 KiB`, above the 16-million floor;
- swap stayed disabled during the arm and memory-full pressure stayed far below
  its limit;
- local read delta peaked at 11,323,424 sectors (5.40 GiB), below the new
  16,777,216-sector allowance;
- root-port corrected-event delta was zero;
- there was no fatal/recoverable link report, controller-down report, OOM, or
  B70 fault;
- all four B70s were idle after teardown and host memory/swap recovered.

The 64-event safety limit will not be raised. There is no A56 retry of this
`twoshots` endpoint: its diagnostic median is already slower, and another
external full load would add hardware stress without a plausible performance
promotion. Subsequent full-model work must reduce local-NVMe runtime and compile
traffic rather than weakening the guard. Optimization returns to one-card,
real-weight component screening, starting with the W13 graph census.

Raw evidence:

- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1-attempt55`;
- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1-attempt55-supervisor`.
