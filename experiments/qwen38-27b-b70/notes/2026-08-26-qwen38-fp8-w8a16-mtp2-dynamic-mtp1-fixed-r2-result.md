# Qwen3.8 FP8 W8A16 dynamic MTP2→MTP1 R2 result

R2 repaired the mixed-width GDN crash, retained single-user performance, and
improved c64 over static MTP2, but it did **not** clear the frozen aggregate
gate. The lane is closed as a measured negative.

## Passed gates

- focused XPU regression: active width 2, padded state width 3, four spec
  decodes; exact output/state comparison passed and padded state slots were
  untouched;
- former c2 crash shape: 256/256 tokens, 2/2 exact sequential token identities,
  engine healthy afterward;
- semantic suite: 7/7 exact plus 8/8 repeat, exactly matching static MTP2;
- first eligible single-user row: **83.161 tok/s after TTFT**, above the
  82.810 preregistered retention gate.

## Aggregate result

- excluded c64 transition: **783.722 tok/s**;
- declared c64: **817.008 tok/s**;
- frozen gate: **875 tok/s**.

The declared batch returned all 8,192 requested tokens with zero cached prompt
tokens and no cross-prompt output collisions. It matched 58/64 sequential token
oracles, so it is an output-isolation-qualified shape variant—not standalone
semantic evidence. The separate semantic suite is the quality gate.

## Why it missed

The server measured only 12,595 KV-cache tokens and reported 49.20× maximum
concurrency at the 256-token cap. During c64 it reached full cache with 49
requests running and 15 waiting. Static MTP1, by contrast, measured 17,956 KV
tokens and 70.14× at the same cap. The dynamic service retains the maximum MTP2
state-row allocation even while its multi-request work uses MTP1.

This is a capacity limit, not another kernel crash. R2 was stopped without
replication or subvariant fishing. The next separately preregistered treatment
changes only the service cap to 192 tokens; the measured benchmark request is
40 prompt + 128 completion tokens (168 total).

Raw evidence and checksums are in
`../data/qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-20260826-r2/`.
