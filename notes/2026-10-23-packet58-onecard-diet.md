# 2026-10-23 — packet58-onecard-diet: exp-diet port to the one-card record line STOPPED at step 1 (layout mismatch)

Packet: `experiments/own-xpu-runtime/stage2/packet58-onecard-diet/`. CPU only; no GPU, `/dev/dri`, unit, PAUSE/STOP/queue
file, sudo or secret touched; nothing queued, launched, committed or submitted. No engine built, no proposal, no
`READY-FOR-DEVICE.json`.

## Brief

Port packet194's exp-diet gate/up kernel (`p193diet::GateUp`, packet193 header, pinned, "do not re-derive") into the one-card
record engine (packet58-onecard-cache23, `083e3853…`, record chain 36.602512 tok/s `cmvkcqznb002lng01fsrhjn7t`) as the
in-load key `expert_gateup=production|diet`, prove exactness on CPU as packet194 did, and screen it on card 0 (K1a, K1b,
one load max23 / max23+diet / max23 / max23+diet / max23). The brief's premise: "the one-card line uses the same expert
dispatch tables as the two-card record (one-card synthesis 1 diffed them byte-identical), so the same kernel applies".

## Finding (06:17–06:20 UTC)

The premise does not hold for the expert gate/up kernel:

* The byte-identical table is `dispatch-speed6.json` (22 `packet26.dispatch.v1` classes; no expert gate/up class). The
  expert kernel is chosen by the `experts` selection key: **one card `wide64+halfcache` → `p58ag::expert` →
  `p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,Cached>`**; two cards `exp-halfcache` → `p49d::expert` Arm 10 →
  `p90exp::Kernel<IQ2_S,2560,64,false,true>` (the kernel packet193 dieted).
* The two kernels read different row formats. One card: `p49bgemv::layout(IQ2_S,2560)` rows, **820 B**, 16-bit halves at
  `halves+2*step` decoded through the 65,536-entry exact halfcache table (20th binding), rows reached through
  `p58::resolve(..., b.indirect)` over expert-cache pointer slots, `p39::validate`. Two cards and the diet header:
  `p90::expert_stride(2560)` = **840 B**, FP32 halves at `halves+4*step`, direct pointers, 19 bindings, `p90exp::validate`
  (refuses any other stride). `p193diet::GateUp` binds through `p90exp::Kernel::bind` and reads
  `bits_float(load32(w+l.halves+4*step))`.
* packet194's own DO-NOT-REPEAT row: "Do not screen the diet on a non-halfcache gate/up layout. The diet is a diet of
  `p90exp::Kernel<IQ2_S,2560,64,wide>` only."

Receipts: `evidence/layout-mismatch.json` (Python proof: 11 source files pinned by sha256, 27 verbatim lines asserted,
both layout formulas transcribed), `evidence/compiler-proof.json` (two `g++ -std=c++20 -fsyntax-only` host TUs against the
real headers: `static_assert(row_bytes==820)` and `static_assert(expert_stride==840)` both compile, 0 warnings, 0.96 s;
run after a `ps comm` check found 0 host compilers — the earlier `pgrep -f icpx` = 1 was the shell matching itself),
`evidence/dnr-grep.txt` (258 DO-NOT-REPEAT files), `evidence/units-poll.json` (only the owner's restore window
`window-p194b-driver` active).

## Decision

STOP and report (the brief's stop rule; the owner's "blocked request: report, don't substitute"). Registering the header
as-is would be refused by the one-card validator or read the wrong bytes; a one-card diet is a new kernel
(`p58ag_exp::wide_chains` with the same three transformations, keeping the table decode and the slot resolution) that needs
packet193's full proof chain (ISA gate, GNU+Intel twins at production shape with halfcache/indirect strata, lane-B device
micro ≤ 0.85× with byte identity on every claimed stratum) before an engine key and a one-card screen. The exactness
argument carries over in substance (`p58ag_exp::decode_tile` is textually `p90exp::decode_tile`; `exceptional ⇔ d
non-finite` holds with `d = halfcache[bits]`); the price is unchanged (11.4 µs per layer = +2 %), but the one-card kernel
pays a table gather and a slot resolution per step that the two-card count does not, so the saving must be measured.

## Next (recommended, not started)

1. Lane-B micro packet (packet193 shape) for `p58ag_diet::GateUp`. 2. If it qualifies, this brief's engine packet:
`expert_gateup` as a one-card view dimension beside `cache_cap`, K1a / K1b / one-load max23 bracket, `s58diet_decision`
with the ruling's bars (≥ +0.5 % screen; ≥ +2 % and ≥ 37.335 chain) and kill rules.
