# Packet110: fresh per-class GPU roofline

Packet107 current QSA, two fresh processes; packet110 current GDN if its clean coordinator receipt is present. Only occupied contexts 128 and 4096 are measured. All numbers below are synthetic complete-layer diagnostics.

**Useful-byte throughput is not measured DRAM bandwidth.** The source model counts distinct useful weight fields and input/state bytes, plus global intermediate reads/writes. Cached duplicate loads, instruction fetch, lookup tables, cache-line overfetch and hardware transactions are not measured. The 537 GB/s copy reference uses total read+write bytes. The difference above this memory-only floor is an opportunity budget, not an attainable speedup.

For each iteration, sum all events for a class before taking its median. Take each process median over exactly 40 post-warm-up calls, then the median of process medians. The JSON retains each process separately. `attention`, `qsa.attention`, `qsa.ik` and `moe` contain multiple events; `small.ffn.q6` includes router/shared gate/up/router. Do not interpret it as a standalone router measurement.

Formulas: GB/s = (read B + write B) / µs / 1000; ratio = GB/s / 537; floor µs = bytes / 537000; above-floor µs = measured µs − floor; headroom ms/half = max(0, above-floor µs) × occurrences / 1000.

Occurrences are 6 QSA and 18 GDN layers per half. This is representative-layer scaling, **not a measured half time**. Layer0 has different formats, and PLE, head, draft, rollback, host gaps and inter-card transfers are excluded. No QSA time is multiplied by 24 or substituted for a GDN time. Packet107 selection retains production expert-down; later down-tile16/composite measurements have a different identity.

GDN status: **measured**. One GDN process is attribution only; it cannot support a speed verdict.

[Machine-readable rows and input hashes](roofline.json); [byte formulas](byte_model.py); [source derivation](BYTE-MODEL.md); [excluded-arm inventory](evidence/exclusions.json).

## QSA, occupied context 128

| Class | Read B/call | Write B/call | µs/call | GB/s | /537 | Floor µs | Above floor µs | × layers | Headroom ms/half |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qsa.attention | 386,312 | 111,364 | 52.083 | 9.56 | 0.018 | 0.927 | 51.156 | 6 | 0.3069 |
| expsgate | 10,757,240 | 25,680 | 59.036 | 182.65 | 0.340 | 20.080 | 38.956 | 6 | 0.2337 |
| expsdown | 9,228,920 | 51,240 | 50.599 | 183.41 | 0.342 | 17.281 | 33.318 | 6 | 0.1999 |
| qsa.qgate | 39,326,720 | 24,576 | 97.187 | 404.90 | 0.754 | 73.280 | 23.907 | 6 | 0.1434 |
| route | 4,392 | 2,664 | 18.750 | 0.38 | 0.001 | 0.013 | 18.737 | 6 | 0.1124 |
| qsa.select | 9,344 | 8,332 | 16.172 | 1.09 | 0.002 | 0.033 | 16.139 | 6 | 0.0968 |
| hc.f.gate | 3,707,520 | 25,600 | 22.083 | 169.05 | 0.315 | 6.952 | 15.131 | 6 | 0.0908 |
| hc.a.gate | 3,707,520 | 25,600 | 21.875 | 170.66 | 0.318 | 6.952 | 14.923 | 6 | 0.0895 |
| ffn.combine | 25,608 | 20,480 | 11.406 | 4.04 | 0.008 | 0.086 | 11.320 | 6 | 0.0679 |
| hc.a.norm | 61,440 | 21,760 | 8.411 | 9.89 | 0.018 | 0.155 | 8.256 | 6 | 0.0495 |
| attention | 19,734,536 | 66,560 | 44.896 | 441.04 | 0.821 | 36.874 | 8.022 | 6 | 0.0481 |
| shexpdown | 1,844,480 | 5,120 | 11.407 | 162.15 | 0.302 | 3.444 | 7.962 | 6 | 0.0478 |
| hc.f.norm | 61,440 | 21,760 | 7.500 | 11.09 | 0.021 | 0.155 | 7.345 | 6 | 0.0441 |
| qsa.k | 1,643,520 | 1,024 | 8.542 | 192.53 | 0.359 | 3.062 | 5.479 | 6 | 0.0329 |
| expsact | 25,600 | 12,800 | 5.417 | 7.09 | 0.013 | 0.072 | 5.345 | 6 | 0.0321 |
| qsa.prepare | 29,312 | 26,624 | 5.364 | 10.43 | 0.019 | 0.104 | 5.260 | 6 | 0.0316 |
| qsa.ik | 662,528 | 2,304 | 6.407 | 103.77 | 0.193 | 1.238 | 5.168 | 6 | 0.0310 |
| qsa.v | 1,643,520 | 1,024 | 8.073 | 203.71 | 0.379 | 3.062 | 5.011 | 6 | 0.0301 |
| moe | 61,486 | 10,240 | 4.870 | 14.73 | 0.027 | 0.134 | 4.736 | 6 | 0.0284 |
| qsa.pool | 3,712 | 2,560 | 4.583 | 1.37 | 0.003 | 0.012 | 4.571 | 6 | 0.0274 |
| qsa.iq | 2,626,560 | 1,024 | 9.245 | 284.22 | 0.529 | 4.893 | 4.352 | 6 | 0.0261 |
| hc.a.low | 3,870,720 | 1,352 | 11.093 | 349.04 | 0.650 | 7.211 | 3.883 | 6 | 0.0233 |
| hc.f.low | 3,870,720 | 1,352 | 10.990 | 352.33 | 0.656 | 7.211 | 3.779 | 6 | 0.0227 |
| shexpact | 2,560 | 1,280 | 3.542 | 1.08 | 0.002 | 0.007 | 3.535 | 6 | 0.0212 |
| small.ffn.q6 | 9,354,240 | 3,586 | 18.958 | 493.60 | 0.919 | 17.426 | 1.532 | 6 | 0.0092 |

## QSA, occupied context 4096

| Class | Read B/call | Write B/call | µs/call | GB/s | /537 | Floor µs | Above floor µs | × layers | Headroom ms/half |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qsa.attention | 5,812,232 | 1,597,444 | 407.683 | 18.18 | 0.034 | 13.798 | 393.884 | 6 | 2.3633 |
| qsa.select | 267,264 | 12,300 | 179.922 | 1.55 | 0.003 | 0.521 | 179.401 | 6 | 1.0764 |
| expsgate | 10,757,240 | 25,680 | 59.635 | 180.81 | 0.337 | 20.080 | 39.555 | 6 | 0.2373 |
| expsdown | 9,228,920 | 51,240 | 50.729 | 182.94 | 0.341 | 17.281 | 33.448 | 6 | 0.2007 |
| qsa.qgate | 39,326,720 | 24,576 | 97.084 | 405.33 | 0.755 | 73.280 | 23.804 | 6 | 0.1428 |
| route | 4,392 | 2,664 | 18.750 | 0.38 | 0.001 | 0.013 | 18.737 | 6 | 0.1124 |
| hc.f.gate | 3,707,520 | 25,600 | 22.917 | 162.90 | 0.303 | 6.952 | 15.965 | 6 | 0.0958 |
| hc.a.gate | 3,707,520 | 25,600 | 21.901 | 170.45 | 0.317 | 6.952 | 14.949 | 6 | 0.0897 |
| attention | 19,734,536 | 66,560 | 50.677 | 390.73 | 0.728 | 36.874 | 13.803 | 6 | 0.0828 |
| ffn.combine | 25,608 | 20,480 | 11.380 | 4.05 | 0.008 | 0.086 | 11.294 | 6 | 0.0678 |
| hc.a.norm | 61,440 | 21,760 | 8.360 | 9.95 | 0.019 | 0.155 | 8.205 | 6 | 0.0492 |
| shexpdown | 1,844,480 | 5,120 | 11.380 | 162.53 | 0.303 | 3.444 | 7.936 | 6 | 0.0476 |
| hc.f.norm | 61,440 | 21,760 | 7.500 | 11.09 | 0.021 | 0.155 | 7.345 | 6 | 0.0441 |
| qsa.k | 1,643,520 | 1,024 | 8.515 | 193.12 | 0.360 | 3.062 | 5.453 | 6 | 0.0327 |
| expsact | 25,600 | 12,800 | 5.495 | 6.99 | 0.013 | 0.072 | 5.423 | 6 | 0.0325 |
| qsa.prepare | 29,312 | 26,624 | 5.364 | 10.43 | 0.019 | 0.104 | 5.260 | 6 | 0.0316 |
| qsa.ik | 662,528 | 2,304 | 6.406 | 103.78 | 0.193 | 1.238 | 5.168 | 6 | 0.0310 |
| qsa.v | 1,643,520 | 1,024 | 8.021 | 205.03 | 0.382 | 3.062 | 4.959 | 6 | 0.0298 |
| hc.f.low | 3,870,720 | 1,352 | 11.979 | 323.22 | 0.602 | 7.211 | 4.769 | 6 | 0.0286 |
| moe | 61,486 | 10,240 | 4.792 | 14.97 | 0.028 | 0.134 | 4.658 | 6 | 0.0280 |
| qsa.pool | 3,712 | 2,560 | 4.636 | 1.35 | 0.003 | 0.012 | 4.624 | 6 | 0.0277 |
| qsa.iq | 2,626,560 | 1,024 | 9.271 | 283.43 | 0.528 | 4.893 | 4.378 | 6 | 0.0263 |
| hc.a.low | 3,870,720 | 1,352 | 11.093 | 349.04 | 0.650 | 7.211 | 3.883 | 6 | 0.0233 |
| shexpact | 2,560 | 1,280 | 3.541 | 1.08 | 0.002 | 0.007 | 3.534 | 6 | 0.0212 |
| small.ffn.q6 | 9,354,240 | 3,586 | 20.390 | 458.94 | 0.855 | 17.426 | 2.964 | 6 | 0.0178 |

## GDN, occupied context 128

| Class | Read B/call | Write B/call | µs/call | GB/s | /537 | Floor µs | Above floor µs | × layers | Headroom ms/half |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| expsgate | 10,757,240 | 25,680 | 60.365 | 178.63 | 0.333 | 20.080 | 40.285 | 18 | 0.7251 |
| expsdown | 9,228,920 | 51,240 | 50.886 | 182.37 | 0.340 | 17.281 | 33.604 | 18 | 0.6049 |
| route | 4,392 | 2,664 | 18.750 | 0.38 | 0.001 | 0.013 | 18.737 | 18 | 0.3373 |
| gdn.recurrence | 1,593,920 | 1,585,152 | 23.958 | 132.69 | 0.247 | 5.920 | 18.038 | 18 | 0.3247 |
| hc.f.gate | 3,707,520 | 25,600 | 22.604 | 165.15 | 0.308 | 6.952 | 15.652 | 18 | 0.2817 |
| hc.a.gate | 3,707,520 | 25,600 | 22.239 | 167.86 | 0.313 | 6.952 | 15.288 | 18 | 0.2752 |
| ffn.combine | 25,608 | 20,480 | 11.354 | 4.06 | 0.008 | 0.086 | 11.268 | 18 | 0.2028 |
| attention | 19,734,536 | 66,560 | 46.666 | 424.31 | 0.790 | 36.874 | 9.793 | 18 | 0.1763 |
| hc.a.norm | 61,440 | 21,760 | 9.791 | 8.50 | 0.016 | 0.155 | 9.636 | 18 | 0.1734 |
| gdn.conv | 245,760 | 81,920 | 9.271 | 35.34 | 0.066 | 0.610 | 8.661 | 18 | 0.1559 |
| shexpdown | 1,844,480 | 5,120 | 11.458 | 161.42 | 0.301 | 3.444 | 8.014 | 18 | 0.1442 |
| gdn.qkv | 32,773,120 | 20,480 | 68.646 | 477.72 | 0.890 | 61.068 | 7.578 | 18 | 0.1364 |
| hc.f.norm | 61,440 | 21,760 | 7.604 | 10.94 | 0.020 | 0.155 | 7.449 | 18 | 0.1341 |
| expsact | 25,600 | 12,800 | 5.417 | 7.09 | 0.013 | 0.072 | 5.345 | 18 | 0.0962 |
| gdn.gated | 25,088 | 12,288 | 5.208 | 7.18 | 0.013 | 0.070 | 5.138 | 18 | 0.0925 |
| small.gdn.ab | 988,160 | 192 | 6.771 | 145.98 | 0.272 | 1.841 | 4.930 | 18 | 0.0887 |
| moe | 61,486 | 10,240 | 5.000 | 14.35 | 0.027 | 0.134 | 4.866 | 18 | 0.0876 |
| shexpact | 2,560 | 1,280 | 3.750 | 1.02 | 0.002 | 0.007 | 3.743 | 18 | 0.0674 |
| hc.f.low | 3,870,720 | 1,352 | 10.833 | 357.43 | 0.666 | 7.211 | 3.622 | 18 | 0.0652 |
| hc.a.low | 3,870,720 | 1,352 | 10.782 | 359.14 | 0.669 | 7.211 | 3.571 | 18 | 0.0643 |
| gdn.z | 19,665,920 | 12,288 | 39.584 | 497.13 | 0.926 | 36.645 | 2.939 | 18 | 0.0529 |
| small.ffn.q6 | 9,354,240 | 3,586 | 18.959 | 493.60 | 0.919 | 17.426 | 1.532 | 18 | 0.0276 |

## GDN, occupied context 4096

| Class | Read B/call | Write B/call | µs/call | GB/s | /537 | Floor µs | Above floor µs | × layers | Headroom ms/half |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| expsgate | 10,757,240 | 25,680 | 60.625 | 177.86 | 0.331 | 20.080 | 40.545 | 18 | 0.7298 |
| expsdown | 9,228,920 | 51,240 | 51.042 | 181.81 | 0.339 | 17.281 | 33.761 | 18 | 0.6077 |
| route | 4,392 | 2,664 | 18.750 | 0.38 | 0.001 | 0.013 | 18.737 | 18 | 0.3373 |
| gdn.recurrence | 1,593,920 | 1,585,152 | 23.959 | 132.69 | 0.247 | 5.920 | 18.039 | 18 | 0.3247 |
| hc.f.gate | 3,707,520 | 25,600 | 22.604 | 165.15 | 0.308 | 6.952 | 15.652 | 18 | 0.2817 |
| hc.a.gate | 3,707,520 | 25,600 | 22.291 | 167.47 | 0.312 | 6.952 | 15.340 | 18 | 0.2761 |
| ffn.combine | 25,608 | 20,480 | 11.354 | 4.06 | 0.008 | 0.086 | 11.268 | 18 | 0.2028 |
| attention | 19,734,536 | 66,560 | 46.667 | 424.31 | 0.790 | 36.874 | 9.793 | 18 | 0.1763 |
| hc.a.norm | 61,440 | 21,760 | 9.792 | 8.50 | 0.016 | 0.155 | 9.637 | 18 | 0.1735 |
| gdn.conv | 245,760 | 81,920 | 9.375 | 34.95 | 0.065 | 0.610 | 8.765 | 18 | 0.1578 |
| shexpdown | 1,844,480 | 5,120 | 11.562 | 159.97 | 0.298 | 3.444 | 8.118 | 18 | 0.1461 |
| gdn.qkv | 32,773,120 | 20,480 | 68.646 | 477.72 | 0.890 | 61.068 | 7.578 | 18 | 0.1364 |
| hc.f.norm | 61,440 | 21,760 | 7.604 | 10.94 | 0.020 | 0.155 | 7.449 | 18 | 0.1341 |
| expsact | 25,600 | 12,800 | 5.416 | 7.09 | 0.013 | 0.072 | 5.344 | 18 | 0.0962 |
| gdn.gated | 25,088 | 12,288 | 5.261 | 7.11 | 0.013 | 0.070 | 5.191 | 18 | 0.0934 |
| small.gdn.ab | 988,160 | 192 | 6.875 | 143.76 | 0.268 | 1.841 | 5.034 | 18 | 0.0906 |
| moe | 61,486 | 10,240 | 5.000 | 14.35 | 0.027 | 0.134 | 4.866 | 18 | 0.0876 |
| shexpact | 2,560 | 1,280 | 3.646 | 1.05 | 0.002 | 0.007 | 3.639 | 18 | 0.0655 |
| hc.f.low | 3,870,720 | 1,352 | 10.833 | 357.43 | 0.666 | 7.211 | 3.622 | 18 | 0.0652 |
| hc.a.low | 3,870,720 | 1,352 | 10.729 | 360.90 | 0.672 | 7.211 | 3.518 | 18 | 0.0633 |
| gdn.z | 19,665,920 | 12,288 | 39.427 | 499.10 | 0.929 | 36.645 | 2.782 | 18 | 0.0501 |
| small.ffn.q6 | 9,354,240 | 3,586 | 18.959 | 493.58 | 0.919 | 17.426 | 1.533 | 18 | 0.0276 |

## Three open exact levers, ranked for the next brief

Rank on the 128-token budget. Feasibility weights are engineering judgements, not measured probabilities or expected gains. The score is headroom × feasibility; 4096-token results remain separate. GDN contributes its fresh representative-layer ×18 budget.

| Rank | Lever | QSA ms/half | GDN ms/half | Available headroom | Feasibility | Score ms/half |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | Exact gate/up tile16 with existing half-cache (packet104b) | 0.2337 | 0.7251 | 0.9589 | 0.65 | 0.6233 |
| 2 | Exact shared-down/mixture/combine and activation epilogues (packet109) | 0.1974 | 0.5983 | 0.7957 | 0.50 | 0.3978 |
| 3 | Pruned top10 selection network after unchanged normalized route probabilities | 0.1124 | 0.3373 | 0.4497 | 0.40 | 0.1799 |

**Exact gate/up tile16 with existing half-cache (packet104b).** Separate open coordinator-authorized gate/up arm. Preserve E1, each chain and BF16 boundary. The 0.892953 operator ratio is only a feasibility clue; the original 15% gate failed and only its explicit screen override permits this arm.

**Exact shared-down/mixture/combine and activation epilogues (packet109).** Prepared complete-tuple epilogues keep rounded intermediates and production NaN behavior. Class headroom is a ceiling; the route body remains unchanged and its 18+ us is deliberately not credited.

**Pruned top10 selection network after unchanged normalized route probabilities.** New mechanism proposal: retain maximum/exp/denominator trees, compare rounded probabilities with ID ties, prune comparisons that cannot affect sorted top10. Distinct from production full bitonic sort and closed all-pairs/geometry arms. Needs a sorting-network proof and exact device gate; no code is implemented here.

Exclusions: packet107 QSA sharing/GDN head-preparation, packet108 draft load8, packet104 non-gate tile arms, packet95/99/102 expert lookup/prefetch/batching, H1 HC cache, packet94 norm-consumer fusion, packet74 packed-dense and packet53b/67 HC geometry remain closed. Route-fast, rec-both-plus and E1 are already in this measurement. Down-tile16 is already banked in newer compositions; its old-control headroom is not a new lever. Q-gate has fresh excess, but its expanded Q6 read floor consumes most of the call; it does not displace these three without a distinct mechanism. No closed arm is reopened by this table.

No lever was implemented or qualified here. The coordinator briefs the winner after checking the latest closure state.
