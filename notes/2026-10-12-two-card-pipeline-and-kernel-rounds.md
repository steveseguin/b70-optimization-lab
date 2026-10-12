# 2026-10-12: both cards working at once, and three kernel rounds (IQ3 own runtime)

Quantized compressed version (Unsloth UD-IQ3_XXS Qwen3.8 Flash-Next), our own runtime,
arithmetic identity `iq3-p17-detmath-v2`. Every model run below reproduced the CPU
oracle exactly (64/64 tokens, 384/384 retained layer fixtures) on cards 0+1 of the
four-B70 host; the kernel log stayed clean all night. Reference to beat: 28.49 tok/s
(llama.cpp SYCL, two cards). Times are UTC.

## Results in order

| When | Packet | What ran | Result |
| --- | --- | --- | --- |
| 00:28–01:28 | [29](../experiments/own-xpu-runtime/stage2/packet29-merged/receipts-cards01-20261012-chain/README.md) | merged kernels (paired expert gate/up, dense variants), one process, sequential | **22.49 tok/s** sealed (44.3 ms per token; GPU kernel time 41.2 ms over 2,307 launches) |
| 02:05 | [33](../experiments/own-xpu-runtime/stage2/packet33-codegen/receipts-card2-20261012-k2/README.md) | kernels designed from the offline GPU assembly, timed on card 2 | routed expert down 127 → 90 µs (first winner in twelve candidates); dense 75 → 62 µs |
| 02:00–03:05 | [32](../experiments/own-xpu-runtime/stage2/packet32-pipeline/receipts-cards01-20261012-chain/README.md) | two processes, one card each, guess-and-verify pipeline | sequential 19.47 tok/s; n-gram guesser 19.64 (4 of 32 guesses right, 28 rollbacks); **diagnostic with every guess right: 26.2 ms mean, 24.1 median per token**; host-memory shadow gone |
| 02:41 | [30](../experiments/own-xpu-runtime/stage2/packet30-leftovers/receipts-card2-20261012-g3/README.md) | route, QSA attention, small GEMVs, merged combine/norm | QSA attention 347 → 117 µs in its fixture; merged combine/norm and route forms 5–10 times slower |
| 02:47 | [34](../experiments/own-xpu-runtime/stage2/packet34-replay-bench/receipts-card3-20261012-r1/README.md) | one half token, 1,142 real launches: one-by-one against a recorded command graph | identical bytes; 19.82 against 19.86 ms: replay is not faster |
| CPU | [31](../experiments/own-xpu-runtime/stage2/packet31-mtp-acceptance/README.md) | official draft head against this target's own tokens | **77.3%** agreement (198 of 256, four prompts; 95% interval 71.8–82.0%) |

## What was learned

1. **Guess-and-verify scheduling is lossless and it works on these cards.** Layers 0–23
   run on one card and 24–47 on the other, so one card was always idle. Now the first
   card starts the next position from a guessed token while the second finishes the
   current one. A wrong guess is discarded (37 alternate state buffers, no copies) and
   the half is redone; the emitted token is always the target's own argmax. The guess
   changes timing only, so there is no tolerance to argue about. Time per token is
   `p*(T/2 + m) + (1-p)*T` for hit rate `p` and guess cost `m`.
2. **One process per card is the right process model.** No shared SYCL context, no peer
   copies, no cross-card events (the leading suspect of the 2026-10-11 09:09 fault), and
   the 55 GB host-memory shadow of the two-device process disappears (GPUActive 17 MB
   after loading).
3. **The token is GPU kernel time.** The host keeps ahead of the card when its issuing
   core is quiet; a recorded launch list replays in the same time; our own per-launch
   host code was 0.1–0.2 µs ([packet 35](../experiments/own-xpu-runtime/stage2/packet35-hostpath/README.md)).
   The earlier "12–18 ms of host issuing" overlapped the GPU work.
4. **Speed measurements on this host need a quiet issuing core.** The same binary and
   dispatch measured 18.9–22.5 tok/s within 30 minutes while CPU-only helper jobs ran 22
   cores of gates and another job read the model file (token preparation page-faulted,
   4–9 ms per token). Decode windows are now pinned to cores 0–3 (+ siblings) and helper
   jobs kept on the others.
5. **Reading the generated GPU code finds kernels; the fitted cost model does not
   predict them.** Offline `ocloc` dumps of the shipped SPIR-V showed where memory
   messages per weight could be cut; the candidates built from that won on the card,
   in a different order than the model predicted.
6. **Merging launches by serialising work inside a kernel loses by 5–10 times.** Only
   merges that keep every lane busy win.
7. **K2's rule for a fusion whose members also win** discarded three measured winners
   (409 extra launches per token). Fixed in packet 35: compare the fusion with the sum of
   the selected members.

## Wrapper defects met on the way (each stopped before any device contact)

- Packet 30: native environment without `LD_LIBRARY_PATH` (no Level Zero device
  visible; reported as "card range") and a false device-fault latch. Fixed by its author.
- Packet 33: a `Path` object in a JSON record. One `str()` by the coordinator, seal
  amended and recorded.
- Packet 34: preflight treated this boot's old, reviewed fault lines as new. A
  coordinator review instant was added by its author.
- Packet 30 (second attempt): preflight demanded the Level Zero loader inside the
  supplied library path. The system library directory was appended to the path.

## Next

1. [Packet 36](../experiments/own-xpu-runtime/stage2/packet36-draft/README.md) (in progress): the official draft head as the guess provider on the second card's process, experts requantised to 8 bits for the draft only. Expected about 32 ms per token (about 31 tok/s) with today's kernels: a right guess about 27 ms, a wrong one about 48 ms.
2. [Packet 37](../experiments/own-xpu-runtime/stage2/packet37-merged2/README.md) (in progress): the pipeline runtime with the packet 33 kernels and the fixed selection rule; then one merge with packet 36, the packet 30 QSA attention, and a native controller (the Python one costs about 4 ms per token).
3. [Packet 39](../experiments/own-xpu-runtime/stage2/packet39-epilogues/README.md) (in progress): element-wise steps folded into the store of the GEMV that feeds them, to remove several hundred of the 1,500 small launches without serial work.
4. Oracles for the other eleven prompts of the reference suite are being generated on CPU, so a sealed speed result can use the same twelve prompts as the reference.

## Later the same day (UTC)

| When | Packet | What ran | Result |
| --- | --- | --- | --- |
| 05:24–05:56 | [36](../experiments/own-xpu-runtime/stage2/packet36-draft/receipts-cards01-20261012-chain/README.md) | official draft head on the second card as the guess provider | **30.37 and 31.02 tok/s**, exact, development prompt; 53 of 63 guesses right; draft host == device |
| 04:20–06:01 | [37](../experiments/own-xpu-runtime/stage2/packet37-merged2/receipts-cards23-20261012-chain/README.md) | pipeline runtime with the packet 33 kernels | sequential 21.50 tok/s; all-right diagnostic 21.3 ms median per token |
| 04:14 | [39](../experiments/own-xpu-runtime/stage2/packet39-epilogues/receipts-card3-20261012-g4/README.md) | epilogue fusions, card 3 | twelve cases exact, about 1.2 ms per token in total |
| 15:20–15:27 | [42](../experiments/own-xpu-runtime/stage2/packet42-codegen2/receipts-card2-20261012/README.md) | launch-floor benchmark and second kernel round, card 2 | a near-empty launch costs 0.5–1.5 µs; first faster route kernel (−1.2 ms per token) |
| 16:04–16:41 | [38](../experiments/own-xpu-runtime/stage2/packet38-integrated/receipts-cards01-20261012-chain/README.md) | integrated runtime, twelve-prompt suite, two repeats | **median 38.25 tok/s, 24 of 24 requests exact**; 39.05 on the development prompt |

Also that day: the root filesystem filled up at 04:57 UTC ([record](../experiments/own-xpu-runtime/stage2/DISK-CLEANUP-20261012.md));
the session waited for a login from 08:50 to 14:23 UTC with nothing running on the cards;
CPU oracles for all twelve prompts were produced (64 tokens and 128 tokens).

More wrapper stops, none a device problem: packet 36 (two build-receipt keys; a race
reading the status of a just-exited child), packet 38 (a 66-length timing grid longer
than its watchdog; a packet-local storage cap that failed a compression step), packet
42 (a compile-smoke path that submitted a kernel with no bound buffer), packet 35 (a
receipt field required in every mode but written in one). Each has an evidence folder
in its packet.
