# Own runtime, IQ3 line: first device answer, the libm finding, and what the parallel kernels cost (2026-10-11, 07:28–08:11 UTC)

Four device windows on this boot, all with clean kernel logs and complete teardown.
Receipts were copied from the ignored `build/` trees into tracked folders.

## 1. First real-model answer on a B70 (packet 13, card 3, one card, layer streaming)

- 87 prompt positions, then 8 generated tokens: **332, 37947, 1653, 10082, 3508, 8812,
  25, 23288** = `**Incident Retrospective: Production`. These are the frozen CPU
  oracle's first eight tokens. Wall time 5,247 s; about 59 s per position, of which
  52 s is the single-work-item non-GEMV interpreter, 0.10 s GEMV, 3.9 s weight streaming.
  Largest terms over the run: `gdn.recurrence` 3,549 s, `qsa.attention` 307 s,
  `gdn.conv` 167 s ([site totals](../experiments/own-xpu-runtime/stage2/packet13-integrate/receipts-card3-20261011-first-token/site-totals.json)).
- **The hidden states are not bit-identical to the CPU oracle: 0 of 48 step-1 layer
  fixtures match.** Layer 0 differs in 4,091 of 10,240 BF16 values (largest 0.00098,
  0.33% relative RMS); layer 47 in 9,914 (5% relative RMS)
  ([comparison](../experiments/own-xpu-runtime/stage2/packet13-integrate/correctness/device-comparison.json)).
  Token agreement is real but it is not the lane's gate.

## 2. Why: the device's elementary functions are not glibc's (packet 15 exactness, card 3)

Packet 15's window runs each of its 72 fixtures three ways: the new parallel kernels on
the card, the packet 4 core on the same card, and the packet 4 core on the host.

- Parallel kernels versus the packet 4 core **on the same card: 72/72**, in two fresh
  owners with identical hashes. The kernels themselves are right.
- Packet 4 core **on the card versus on the host: 50/72**. Every differing case
  contains `exp`, `log`, a `1/sqrt` chain or trig (GDN gates 18–512 bytes, router
  softmax 10–345, combine+norm 12–99, QSA attention 48–55,800 at 87 rows); every case
  without them matches (conv, plain norm, activations, MoE combine, pooling, selection)
  ([diagnostics](../experiments/own-xpu-runtime/stage2/packet15-nongemv/receipts-card3-20261011/exact-b/owner0/arithmetic-diagnostics.jsonl)).

So arithmetic identity v1, which says "scalar FP32 libm", names something the GPU does
not have. This was the open risk recorded in
[the packet 15 gate note](2026-10-11-packet15-gate-authority.md); it is now measured.
Build flags were already `-fno-fast-math -ffp-contract=off -fdenormal-fp-math=ieee`.

**Decision (coordinator, recorded for the owner to judge).** No tolerance is introduced
and the device is not declared its own authority. Identity **v2** replaces the library
calls with our own deterministic `exp`/`log` (a fixed sequence of binary32 operations
with explicit `fma`), a host-generated RoPE table as a model constant, and the `1/sqrt`
spelling that a device census proves exact. The CPU oracle is re-based on v2 and the
device must then reproduce it bit for bit; that includes a host-versus-device gate on
the 72 fixtures, which v1 cannot pass. Work is in `stage2/packet17-detmath`
(Codex, CPU only). v1 results stay as evidence. This changes low-order bits of hidden
states relative to v1; the 64-token answer is expected to stay the same and will be
reported either way.

## 3. What the parallel non-GEMV kernels cost (packet 15 timing, card 3, two owners)

| Layer kind, one new token | Before (packet 13, measured) | Parallel kernels | Launches |
| --- | ---: | ---: | ---: |
| GDN layer, non-GEMV device time | about 1,220 ms | **0.461 ms** (0.612 ms wall) | 14 |
| QSA layer, non-GEMV device time | about 660 ms | **0.555 ms** (0.763 ms wall) | 17 |

Per token (36 GDN + 12 QSA layers): about **23 ms device / 31 ms wall**, down from
about 52,000 ms. That is no longer negligible beside the 41 ms GEMV projection:
sequential two-card decode projects to roughly 64–72 ms per token (14–16 tok/s) before
any further work, against the 28.49 tok/s reference. Inside the 23 ms the largest
single kernel is route+gather at **0.230 ms per layer (11 ms per token)**, then GDN
recurrence 0.109 ms (3.9 ms per token) and QSA attention 0.144 ms; the many
elementwise kernels are 3–7 µs each. These are synthetic operator sequences at one
row, not a decode measurement
([summary](../experiments/own-xpu-runtime/stage2/packet15-nongemv/receipts-card3-20261011/timing-a/summary.json)).

## 4. Within-layer two-card split is exact on the cards, and its exchanges are too many (packet 14, cards 2+3)

- Attempt a refused on the host before any device work: the one-layer plan was checked
  for whole-model tensor coverage ([note](../experiments/own-xpu-runtime/stage2/packet14-tp2/evidence/20261011-layer-a-plan-coverage/COORDINATOR-NOTE.md)).
  Fixed in `write_plan`; the fixed host build reproduces the one-card CPU layer-0 hash
  `1b7f914b…` on the real model.
- Attempt b: all 87 prompt positions through layer 0 on two cards, **bit-identical to
  the one-card device result** (`ab1bbb5a…`), clean teardown of both owners.
- Cost per layer at the last position: GEMV 0.97 ms summed over both cards (about
  0.5 ms each, in parallel), but **41 peer exchanges costing 1.53 ms wall** and
  198,608 bytes. The exchange time is larger than the GEMV time it saves, so the split
  only pays after the exchanges are merged into a few per layer.
  ([receipts](../experiments/own-xpu-runtime/stage2/packet14-tp2/receipts-cards23-20261011-layer/window.json))
- The two-card first-token gate is deferred: with the old interpreter it would hold two
  cards for about 85 minutes; with the parallel kernels it takes minutes.

## Mistakes made in this session

- The first packet 15 launch ran without the oneAPI environment; the child died on
  `libsycl.so.9` before opening a device, and the wrapper still wrote a latch and
  `device_executed: true`. Preserved under `receipts-card3-20261011/exact-a-loader-error`.
  New wrappers must run `ldd` before creating a latch.

## Next, in order

1. Packet 16 (two-card resident decode with the parallel kernels and chained events):
   first measured decode tok/s.
2. Packet 17 device windows (census, deterministic math host/device equality), then the
   v2 oracle gate on the full model.
3. Route+gather kernel (11 ms per token) and merging adjacent non-GEMV launches.
4. Merge packet 14's 41 exchanges per layer into a few, then repeat its gate.

## Addendum, 09:20 UTC: link-line flags, packet 16 one-card pass, and a fault halt

- **The exactness gap has a second, larger cause.** Packet 17's W-B stopped on one
  input (`log(1 − 2^-23)`, one unit in the last place). Rebuilding the same source one
  step at a time showed that `-foffload-fp32-prec-div -foffload-fp32-prec-sqrt` must be
  on the link command; on the compile line alone they do nothing. Linked correctly,
  `exp-v2` and `log-v2` equal the host on the card for all 2^32 inputs each
  ([forensics](../experiments/own-xpu-runtime/stage2/packet17-detmath/evidence/20261011-wb-a-link-flags/README.md)).
  Every device binary through packet 16 therefore also had approximate divide and sqrt.
- **v2 oracle.** `exp`/`log` within 0.50000005 ULP of the true value, identical under
  both host compilers. Against the v1 oracle: 41 of 64 tokens equal, first difference at
  token 42 where v2's two leading logits tie exactly at 22.0 (v1: 22.0 versus 21.875).
  Both texts are coherent. This is the output change recorded for the owner.
- **Packet 16 W1 (card 3):** the chained runtime with parallel kernels reproduces packet
  13's device result (48/48 layers, token 332) in 485 s. Per position 71–92 ms GEMV and
  81–112 ms non-GEMV device time over 3,619 launches: launch count, not arithmetic, is
  now the main cost.
- **Fault halt, 09:09:45 UTC.** My two-card resident speed run (W2's command without
  the oracle argument, plus a NEO host-memory key) page-faulted and engine-reset both
  cards at first compute. Second fault on this boot, so device launches are stopped and
  the reboot is the owner's decision
  ([incident](../experiments/own-xpu-runtime/stage2/packet16-decode/evidence/20261011-w2x-two-card-fault/README.md)).
  My error: the chained path had only ever run under a synchronous CPU mock, and I
  started it at full size and changed two things relative to the prepared window.
  Packet 19 builds the CPU sanitizer that closes that hole.
