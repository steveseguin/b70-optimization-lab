# Packet58-onecard-diet: port of the exp-diet gate/up kernel to the one-card record line — STOPPED at step 1 (layout mismatch)

**Status (2026-10-23 06:20 UTC, CPU only): STOPPED before any build.** packet193's `exp-diet` header (`p193diet::GateUp`) is a
diet of the **two-card** gate/up kernel `p90exp::Kernel<IQ2_S,2560,64,false,true>` and binds to that kernel's row format
(840-byte FP32-expanded rows, direct pointers, 19 bindings). The **one-card record line** (packet58-onecard-cache23 /
-chain, selection `experts=wide64+halfcache`) dispatches a different kernel, `p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,
Cached=true>`, on **820-byte rows with 16-bit halves decoded through a 65,536-entry halfcache table (binding 20) and
indirect expert-cache pointer slots (`p58::resolve`)**. The header cannot be registered as-is; a one-card diet would be a
new kernel, which the brief forbids ("copy the header with its pin; do not re-derive"). Per the brief's stop rule the
packet reports instead of substituting. **No engine was built, no proposal or `READY-FOR-DEVICE.json` was written, nothing
was queued, launched, committed or touched on the device.** The only compiler use was two syntax-only host `g++` TUs
(0.96 s total, 0 warnings) that receipt the two strides from the real headers, run after a non-self-matching check that no
other host compiler was active (`evidence/compiler-proof.json`).

Line: Qwen3.8 Flash-Next 125B-A6B UD-IQ3_XXS, own Xe runtime, one B70 (card 0, lane A), 128-token capped suite, oracle
`iq3-p49-split32-v1`. Record: **36.602512 tok/s** (packet58-onecard-cache23-chain, LocalMaxxing `cmvkcqznb002lng01fsrhjn7t`),
engine `083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a`, `cache_cap max23`.

## Coordinator ruling (quoted)

> "packet194 measured the exact gate/up instruction diet at +1.96 % in the two-card engine with every view exact. Port it to
> the one-card record line (packet58-onecard-cache23 engine) as the same in-load key `expert_gateup=production|diet`, prove
> engine-level exactness on CPU as packet194 did, and screen it on card 0 with K1a, K1b, then one load max23 / max23+diet /
> max23 / max23+diet / max23. Screen winner at ≥ +0.5 % over every warm control view; chain rule at ≥ +2 % over every
> control view AND ≥ 37.335 (1.02 × 36.602512). Kill rules: any inexact view; DRM > 30.5 GB (unchanged guard); control drift
> > 3 % or warm control < 36.0 (host disturbed, no auto-rerun); gate/up saving < 5 µs per layer."

## What the sources say (`stride_proof.py` → `evidence/layout-mismatch.json`; `evidence/compiler-proof.json`)

| | One-card record line (packet58-onecard-cache23 engine) | Two-card record line (packet189/194 engine) | packet193 `p193diet::GateUp` (exp-diet) |
|---|---|---|---|
| Selection key | `experts=wide64+halfcache` (`runtime-selection.json` of the screen and of the chain) | `experts=exp-halfcache+down-tile16` (19/20-key k3x selection) | selected by `expert_gateup=diet` at exp-halfcache sites |
| Dispatch | `main.cpp`: `p58ag::expert(dev(c),selected,b,halfcache,a.experts=="wide64+halfcache")` → `p58ag_submit.cpp` | `p49d::expert(..., choice, gateup)` → `chosen_expert<13>` (packet194 Arm 13) | registered beside Arm 10 `p90exp::Kernel` |
| Kernel | `p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,Cached>` | `p90exp::Kernel<IQ2_S,2560,64,false,true>` | `using Production=p90exp::Kernel<...>`; binds through `Production::bind` |
| Row stride | **820 B** = `p49bgemv::layout(IQ2_S,2560).row_bytes` (`p49d_expert.hpp`: `b.rb=p49bgemv::layout(T,K).row_bytes`) | **840 B** = `p90::expert_stride(2560)` = `halves+4*(k/256)` | **840 B** (`b.rb=p90::expert_stride(K)`; `p90exp::validate` refuses any other `rb`) |
| Block scale (`d`) | 16-bit half at `halves+2*step`, decoded as `halfcache[bits]` (exact FP32 table, `p[19]`, `extent(halfcache,65536*4)`) or `iq3::half(bits)` | FP32 at `halves+4*step` (`bits_float(load32(...))`, expanded at load) | FP32 at `halves+4*step` (`const float d=iq3::bits_float(p49bgemv::load32(w+l.halves+4*step))`) |
| Row address | `p58::resolve(stream?b.peer:b.w, source*rb, rows*rb, b.indirect)` over `p58::Pointer` expert-cache slots (`b.indirect=caching()&&(l.op=="expert_gate_up"||...)`) | direct `(stream?b.peer:b.w)+source*b.rb` | direct `(stream?b.peer:b.w)+source*b.rb` |
| Bindings | 20 (`std::array<ownrt::Allocation,20> ids{..., halfcache}`) | 19 | 19 (no halfcache, no `indirect`) |
| Validation | `p39::validate` (rb = 820) | `p90exp::validate` (rb = 840) | `p90exp::validate` (rb = 840) |

Compiler receipt: `static_assert(p49bgemv::layout(IQ2_S,2560).row_bytes==820)` against packet58j's `p49b_gemv.hpp` and
`static_assert(p90::expert_stride(2560)==840)` against packet193's pinned `p90_layout.hpp` both compile (`g++ -std=c++20
-fsyntax-only`, host-only). The Python proof pins the eleven source files by sha256 and asserts 27 load-bearing lines verbatim.

**Premise check.** The brief's "the one-card line uses the same expert dispatch tables as the two-card record (one-card
synthesis 1 diffed them byte-identical)" refers to `dispatch-speed6.json` (22 `packet26.dispatch.v1` classes: norms, GDN,
QSA, route, combine, ...; the only ffn entry is `ffn.combine: specialised`). The expert gate/up kernel is not in that
table: it is chosen by the `experts` selection key, `wide64+halfcache` on one card (packet58ag's port with the half-decode
table and the expert-cache pointer slots) and `exp-halfcache` on two cards (expanded rows). packet194's own boundary row
already says it: "**Do not screen the diet on a non-halfcache gate/up layout.** The diet is a diet of
`p90exp::Kernel<IQ2_S,2560,64,wide>` only; the engine refuses it elsewhere" (`../packet194-expert-diet-engine/DO-NOT-REPEAT.md`).

## Why this is a STOP, not a port

* Registering `p193diet::GateUp` as a one-card arm would either be refused by the one-card validator (`rb` 820 ≠ 840) or,
  with the validator bypassed, read the 16-bit half and the next row's bytes as an FP32 scale and read pointer-slot
  words as weights: not a diet of the record kernel, not exact, not the thing packet193/194 proved.
* Writing a one-card diet (the same three transformations — hoisted uniform `exceptional`, sign after the scale multiply,
  CSE'd effective scales — applied to `p58ag_exp::wide_chains`, keeping the 16-bit half load + table decode, the
  `p58::resolve` slot resolution and the 20th binding) is a **re-derivation**: a new kernel that needs packet193's full
  proof chain (offline ISA count with 0 spills, GNU + Intel host twins at production shape on real rows plus
  indirect-slot and halfcache strata, a lane-B device micro at ≤ 0.85× cold and warm with byte identity on every claimed
  stratum) before an engine key and a one-card screen. The brief forbids it here and the owner's rule is to report a
  blocked ask, not to deploy a different setup.
* The exactness argument itself (packet193 README §2) carries over to that future kernel unchanged in substance:
  `p58ag_exp::decode_tile` is textually the same as `p90exp::decode_tile`; with `d = halfcache[bits]` (the exact decode of
  the same half) `exceptional ⇔ d non-finite` still holds per 256-weight step, the grid magnitudes are still {8, 25, 43},
  and the chain arithmetic is the same FP32 sequence. The price is also unchanged: 11.4 µs per layer = +2 % over 48
  serial layer bodies (packet194 measured 10.8–11.8 µs per layer on the two-card kernel; the one-card kernel's scale path
  is a table gather instead of an FP32 load, so its saving must be measured, not assumed).

## Gates run (all CPU; receipts under `evidence/`)

| Gate | Result | Receipt |
|---|---|---|
| DO-NOT-REPEAT grep (every `DO-NOT-REPEAT.md` under stage2, 258 files) | packet194's "non-halfcache gate/up layout" boundary found; no row closes a one-card diet (none exists) | `evidence/dnr-grep.txt` |
| Unit / compiler poll before the only compile | active: the owner's endpoint-restore window `window-p194b-driver` (tolerated, packet193/194 precedent); 0 host compiler processes by `ps comm` (the earlier `pgrep -f icpx` count of 1 was this shell matching itself) | `evidence/units-poll.json`, `evidence/compiler-proof.json` |
| Stride / binding proof (Python, 11 files pinned by sha256, 27 verbatim lines asserted) | PASS: one card 820 B / 2-byte halves / 20 bindings / indirect; two cards and the diet 840 B / 4-byte halves / 19 bindings / direct | `evidence/layout-mismatch.json` |
| Compiler receipt (2 × `g++ -fsyntax-only`, host-only, real headers) | PASS: both `static_assert`s compile, 0 warnings, 0.49 + 0.47 s | `evidence/compiler-proof.json`, `build/*.cpp` |

**Not run, on purpose (nothing to gate):** engine build / relink, kernel-identity gate, diet dispatch fixture,
production-shape startup, byte-identity for `production`, admission, analysis tests, safety/exec-limits/loader, seal,
`package_rows`, `check_queue_rows`, private-copy `lanequeue.py plan`, pin guard, `final_checks --ready`. No proposal file
(`ops/lane-queue/proposed-p58-diet-one-card-A.txt` does not exist), no `READY-FOR-DEVICE.json`, no binary, no
`s58diet_decision` (its inputs would be a screen that cannot be built from this header).

## Rows, memory, disk

* Rows: **none proposed.** Host admission, DRM projection and the memory plan of the record line are untouched
  (packet58-onecard-cache23: host 100,487,123,456 B, DRM projection 29,943,603,712 B under the 30.5 GB guard).
* Disk: root free 29,272,612,864 B at start, 29,213,265,920 B after the poll receipts (the packet is ~60 KB; `build/` holds
  two 200-byte sources). Nothing under 27 GB was approached.

## What a real one-card diet packet would be (recommendation, not started)

1. **Micro packet (lane B, packet193 shape):** `p58ag_diet::GateUp` beside the pinned `p58ag_expert.hpp`; ISA gate on
   BMG-G31 through packet81's ocloc pipeline (the one-card kernel's dynamic instruction count per weight is unknown — the
   table gather for `d` and the slot resolution are extra instructions the two-card count does not have); GNU + Intel host
   twins on packet162b real rows with the halfcache table and indirect-slot banks; device byte identity + ≤ 0.85× cold and
   warm in both orders. Price: the brief's 11.4 µs per layer = +2 %.
2. **Engine packet (this brief's shape):** `expert_gateup=production|diet` as a one-card view dimension beside
   `cache_cap` in `bracket_table.hpp` / `main.cpp` (`p58ag::expert` gains the key; `production` byte-for-byte; per-kernel
   SPIR-V identity of the rebuilt `p58ag_submit.o`), the K1a / K1b / one-load max23 bracket, `s58diet_decision` with the
   ruling's bars (≥ +0.5 % screen, ≥ +2 % and ≥ 37.335 chain) and kill rules (inexact view, DRM > 30.5 GB, drift > 3 %, warm
   control < 36.0, saving < 5 µs per layer).

[Boundaries](DO-NOT-REPEAT.md) · [Retention](RETENTION.md) · note `notes/2026-10-23-packet58-onecard-diet.md` ·
parents `../packet58-onecard-cache23/README.md`, `../packet58-onecard-cache23-chain/README.md`,
`../packet193-expert-diet/README.md`, `../packet194-expert-diet-engine/README.md`.
