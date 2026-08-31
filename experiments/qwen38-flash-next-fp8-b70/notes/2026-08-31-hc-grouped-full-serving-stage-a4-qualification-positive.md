# Qwen3.8 Flash-Next grouped full-serving stage A4 qualification result

Date: 2026-08-31
Status: PASS; component-qualified package, endpoint not yet tested

The A2 hybrid serving package passed its complete A4 qualification in about
130 seconds. The run launched no server, loaded no full checkpoint, measured no
endpoint throughput, consumed no full-load boot marker, and required no reboot.

Passed gates:

- clean-process package/loader validation preserved all 32 accepted schemas,
  removed none, and admitted exactly the 14 frozen additions in the pinned
  kernel chain; candidate count is 46 and GDN retains its 23-argument ABI;
- 5/5 grouped-HyperConnection focused tests and 25/25 Qwen config tests;
- GDN preflight/smoke and two fresh 100-trajectory, 6,400-call history arms,
  with exact canonical-chunk equality across both arms;
- exact M1 map resolution to eight warps and 100 real layer-0/rank-0 checkpoint
  repeats with one retained output digest,
  `eb1a25f96c14a3343494d2c240b9033b9dffd386d295c73b588b5e5b08d3b718`;
- all four B70 single-device and TP4 health receipts, plus 100 BF16
  `[1,2560]` reductions with one identical digest on ranks 0--3;
- unchanged postflight card identity, no render-node owner, readable/clean
  bounded kernel journal, and exact stage/build closure throughout.

The external evidence directory is
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/grouped-serving-stage-eeee7d6-a2-qualification-a4`.
Its self-excluding evidence-manifest SHA-256 is
`ca218488129510e0bc29175f96fd17f0572ecbc2e0f7913ce3c576d25b5b3591`.

This pass qualifies the package components and authorizes freezing A30. It does
not yet prove that grouped HyperConnection engages correctly in the full
173 GB model, improves endpoint speed, or preserves the complete response
battery. A30 must therefore remain candidate-only and retain the protected
`5.515783 tok/s` MTP0 and approximately `20.727 tok/s` MTP4 results unchanged.
Attribution still requires a matched new-stage flag-off control and a fresh
flag-on repeat after the composite endpoint candidate.

