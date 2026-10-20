# Packet175b negative-result index (D1 dense-lane scale-word multicast)

No device result exists yet, and this preparation closes nothing. The analyzer
appends a measured closure only after complete exact device coverage: 240
interleaved A/B pairs per layer, with every timed arm byte-checked. It closes D1
only if the weighted dense GEMV time B/A is above 0.97 (coordinator review 44).
D1's overhead is inside the dense events. Synthetic adapter closures live only
under `evidence/private-report-cases/` and are not device conclusions.

Checked before work (see `evidence/do-not-repeat-search.txt`):

* **packet140 N1 and packet58ao.** Scale multicast was ranked below the +3% and +2%
  admissions on CPU priors only, with no implementation or device result. The
  revisit condition is class-matched causal evidence of a net saving, including the
  replacement work. This micro supplies that evidence.
* **packet81.** Halving the static load counts was engine-neutral. This is negative
  evidence for load-issue cuts.
* **packet108.** The INT8 eight-value-load micro measured 0.993× and 0.901×.
* **packet25 and packet11.** Their scale-hoisting rows concern IQ metadata decode,
  not the dense Q6_K/Q8_0 lane.
* **qwen38-27b.** Its SIMD32 shuffle collective (−3.07%) is a different, vLLM Q8 RMS
  tail mechanism.

| Arm | Outcome | Evidence | Revisit condition |
| --- | --- | --- | --- |
| D1 same-bit scale-word multicast in the dense lane (one owner load per 32-word chunk + select_from_group; packet175 harness, real packet166 M1 launch order + 256 MiB interposer) | packet175b device micro: weighted dense GEMV B/A 1.0665 > 0.97 (reduction -6.65%); changed-site B/A per layer L0 1.0766, L3 1.1429; paired p10/p90 per layer L0 0.9915/1.1079, L3 1.0906/1.0963. Evidence /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet175b-twocard-d1-micro/evidence/d1-micro-B1. | Native evidence of a scale-load issue stall in the dense lane AND a different multicast mechanism with a measured dense GEMV B/A <= 0.97. |
