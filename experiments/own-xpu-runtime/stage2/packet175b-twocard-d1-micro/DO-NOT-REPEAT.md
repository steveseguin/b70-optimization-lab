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
