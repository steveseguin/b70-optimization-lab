# Packet72 in-engine bandwidth audit

Measured packet64 lane-B site times, recomputed from the raw events. No GPU or model run. Read numerator uses the real runtime representation of every tensor, plus distinct activation/state and inter-kernel scratch reads. Writes are retained separately in JSON and excluded from this read-bandwidth denominator.

**This is effective read bandwidth in the engine, not a hardware DRAM counter.** sites.jsonl contains timestamps, not memory transactions. Actual cache misses, repeated loads served by cache, line overfetch and physical DRAM bytes cannot be recovered on CPU. The distinction matters: counting every source-level activation load against a DRAM ceiling would yield impossible rates above that ceiling. No claim of measured physical DRAM traffic is made.

The independently regrouped timing sums all events per (prompt, rank, fixture, label), then takes the call median. Only corrected/target, non-speculative calls are included. Rank0 samples are miss-conditioned. The trace samples layers22/23 and24/27, not all48 layers. The all-layer inventory preserves actual tensor types and leaves unsampled times null. Occurrence-weighted half costs are estimates from those samples, not directly measured half totals.

555 GB/s is the requested reference, not a proven achievable floor for these compute-heavy sites. Headroom = occurrences * (call_us - read_bytes / 555000). Qualify only >=300 us in at least one half, retaining both ranks separately. No averaging ranks to manufacture qualification.

Q6_K is expanded to signed8 codes plus one F32 scale per16 elements; Q8_0 uses one per32. For example QKV reads32.768 MB of runtime weights, not21.504 MB of packed GGUF. Most dense projections are already around500 GB/s. Source layout: packet70 p49b_gemv.hpp, p49c_kernel.hpp and p60_kernels.hpp. Byte formulas are retained from and reviewed against packet67 audit.py, with read-only denominator corrected here; they are minimum distinct reads, not issued-load counts.

| Rank | Site | Read GB/s (weighted) | Reference % | ms/half | Headroom ms/half | Qualifies |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 0 | expsgate | 144.20 | 26.0 | 1.7478 | 1.2937 | yes |
| 0 | expsdown | 161.97 | 29.2 | 1.3675 | 0.9684 | yes |
| 0 | gdn.recurrence | 44.48 | 8.0 | 0.6450 | 0.5933 | yes |
| 0 | route | 0.23 | 0.0 | 0.4644 | 0.4642 | yes |
| 0 | hc.f.gate | 148.30 | 26.7 | 0.6000 | 0.4397 | yes |
| 0 | hc.a.gate | 148.61 | 26.8 | 0.5988 | 0.4384 | yes |
| 0 | ffn.combine | 2.31 | 0.4 | 0.2659 | 0.2648 | no |
| 0 | qsa.attention | 5.91 | 1.1 | 0.2669 | 0.2640 | no |
| 0 | attention | 425.37 | 76.6 | 1.1134 | 0.2601 | no |
| 0 | hc.a.norm | 7.90 | 1.4 | 0.1866 | 0.1839 | no |
| 0 | shexpdown | 168.44 | 30.3 | 0.2628 | 0.1831 | no |
| 0 | hc.f.norm | 8.03 | 1.4 | 0.1837 | 0.1811 | no |
| 0 | moe | 9.92 | 1.8 | 0.1488 | 0.1461 | no |
| 0 | hc.f.low | 304.27 | 54.8 | 0.3053 | 0.1379 | no |
| 0 | expsact | 4.54 | 0.8 | 0.1353 | 0.1342 | no |
| 0 | router | 423.34 | 76.3 | 0.5303 | 0.1258 | no |
| 0 | gdn.conv | 33.70 | 6.1 | 0.1313 | 0.1233 | no |
| 0 | gdn.qkv | 500.59 | 90.2 | 1.1784 | 0.1155 | no |
| 0 | hc.a.low | 344.06 | 62.0 | 0.2700 | 0.1026 | no |
| 0 | shexpact | 0.61 | 0.1 | 0.1003 | 0.1002 | no |
| 0 | gdn.gated | 4.54 | 0.8 | 0.0994 | 0.0986 | no |
| 0 | gdn.a | 148.23 | 26.7 | 0.1200 | 0.0879 | no |
| 0 | qsa.select | 0.43 | 0.1 | 0.0869 | 0.0868 | no |
| 0 | gdn.z | 500.77 | 90.2 | 0.7069 | 0.0691 | no |
| 0 | qsa.qgate | 510.87 | 92.0 | 0.4619 | 0.0367 | no |
| 0 | qsa.k | 194.80 | 35.1 | 0.0506 | 0.0329 | no |
| 0 | qsa.v | 197.23 | 35.5 | 0.0500 | 0.0322 | no |
| 0 | qsa.ik | 104.27 | 18.8 | 0.0381 | 0.0310 | no |
| 0 | qsa.prepare | 5.86 | 1.1 | 0.0300 | 0.0297 | no |
| 0 | qsa.iq | 289.83 | 52.2 | 0.0544 | 0.0260 | no |
| 0 | qsa.pool | 0.78 | 0.1 | 0.0178 | 0.0178 | no |
| 1 | expsgate | 143.05 | 25.8 | 1.7619 | 1.3078 | yes |
| 1 | expsdown | 159.85 | 28.8 | 1.3856 | 0.9865 | yes |
| 1 | gdn.recurrence | 45.68 | 8.2 | 0.6281 | 0.5764 | yes |
| 1 | route | 0.22 | 0.0 | 0.4784 | 0.4782 | yes |
| 1 | hc.a.gate | 148.61 | 26.8 | 0.5988 | 0.4384 | yes |
| 1 | hc.f.gate | 149.39 | 26.9 | 0.5956 | 0.4353 | yes |
| 1 | attention | 407.21 | 73.4 | 1.1631 | 0.3097 | yes |
| 1 | qsa.attention | 5.87 | 1.1 | 0.2691 | 0.2662 | no |
| 1 | ffn.combine | 2.32 | 0.4 | 0.2650 | 0.2639 | no |
| 1 | hc.a.norm | 6.60 | 1.2 | 0.2234 | 0.2208 | no |
| 1 | shexpdown | 163.95 | 29.5 | 0.2700 | 0.1902 | no |
| 1 | hc.f.norm | 7.86 | 1.4 | 0.1875 | 0.1848 | no |
| 1 | moe | 9.56 | 1.7 | 0.1544 | 0.1517 | no |
| 1 | expsact | 4.53 | 0.8 | 0.1356 | 0.1345 | no |
| 1 | gdn.conv | 33.23 | 6.0 | 0.1331 | 0.1252 | no |
| 1 | router | 424.58 | 76.5 | 0.5288 | 0.1243 | no |
| 1 | hc.a.low | 331.77 | 59.8 | 0.2800 | 0.1126 | no |
| 1 | hc.f.low | 332.90 | 60.0 | 0.2791 | 0.1117 | no |
| 1 | gdn.gated | 4.46 | 0.8 | 0.1013 | 0.1004 | no |
| 1 | shexpact | 0.61 | 0.1 | 0.1000 | 0.0999 | no |
| 1 | gdn.a | 143.73 | 25.9 | 0.1237 | 0.0917 | no |
| 1 | qsa.select | 0.43 | 0.1 | 0.0862 | 0.0862 | no |
| 1 | gdn.qkv | 514.09 | 92.6 | 1.1475 | 0.0846 | no |
| 1 | gdn.z | 498.14 | 89.8 | 0.7106 | 0.0728 | no |
| 1 | qsa.qgate | 508.12 | 91.6 | 0.4644 | 0.0392 | no |
| 1 | qsa.k | 190.09 | 34.3 | 0.0519 | 0.0341 | no |
| 1 | qsa.v | 194.80 | 35.1 | 0.0506 | 0.0329 | no |
| 1 | qsa.ik | 102.60 | 18.5 | 0.0387 | 0.0316 | no |
| 1 | qsa.prepare | 5.63 | 1.0 | 0.0312 | 0.0309 | no |
| 1 | qsa.iq | 286.55 | 51.6 | 0.0550 | 0.0266 | no |
| 1 | qsa.pool | 0.69 | 0.1 | 0.0200 | 0.0200 | no |

## Every measured layer site

| Rank/layer | Site | Runtime weight read B | Other read B | Writes B | Call us | Read GB/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0/22 | attention | 19,660,800 | 73,736 | 66,560 | 46.511 | 424.30 |
| 0/22 | expsact | 0 | 25,600 | 12,800 | 5.677 | 4.51 |
| 0/22 | expsdown | 9,216,000 | 12,920 | 51,240 | 56.979 | 161.97 |
| 0/22 | expsgate | 10,496,000 | 5,240 | 25,680 | 72.864 | 144.12 |
| 0/22 | ffn.combine | 0 | 25,608 | 20,480 | 11.042 | 2.32 |
| 0/22 | gdn.a | 983,040 | 5,120 | 192 | 6.667 | 148.23 |
| 0/22 | gdn.conv | 163,840 | 81,920 | 81,920 | 7.292 | 33.70 |
| 0/22 | gdn.gated | 512 | 24,576 | 12,288 | 5.521 | 4.54 |
| 0/22 | gdn.qkv | 32,768,000 | 5,120 | 20,480 | 65.469 | 500.59 |
| 0/22 | gdn.recurrence | 384 | 1,593,536 | 1,585,152 | 35.833 | 44.48 |
| 0/22 | gdn.z | 19,660,800 | 5,120 | 12,288 | 39.271 | 500.77 |
| 0/22 | hc.a.gate | 3,686,400 | 21,120 | 25,600 | 24.792 | 149.55 |
| 0/22 | hc.a.low | 3,850,240 | 20,480 | 1,352 | 11.250 | 344.06 |
| 0/22 | hc.a.norm | 40,960 | 20,480 | 21,760 | 7.761 | 7.92 |
| 0/22 | hc.f.gate | 3,686,400 | 21,120 | 25,600 | 24.792 | 149.55 |
| 0/22 | hc.f.low | 3,850,240 | 20,480 | 1,352 | 13.073 | 296.09 |
| 0/22 | hc.f.norm | 40,960 | 20,480 | 21,760 | 7.604 | 8.08 |
| 0/22 | moe | 0 | 61,486 | 10,240 | 6.146 | 10.00 |
| 0/22 | route | 0 | 4,392 | 2,664 | 19.376 | 0.23 |
| 0/22 | router | 9,349,120 | 5,120 | 3,586 | 22.136 | 422.59 |
| 0/22 | shexpact | 0 | 2,560 | 1,280 | 4.063 | 0.63 |
| 0/22 | shexpdown | 1,843,200 | 1,280 | 5,120 | 10.938 | 168.64 |
| 0/23 | attention | 19,660,800 | 73,736 | 66,560 | 46.042 | 428.62 |
| 0/23 | expsact | 0 | 25,600 | 12,800 | 5.521 | 4.64 |
| 0/23 | expsdown | 9,216,000 | 12,920 | 51,240 | 56.979 | 161.97 |
| 0/23 | expsgate | 10,496,000 | 5,240 | 25,680 | 72.708 | 144.43 |
| 0/23 | ffn.combine | 0 | 25,608 | 20,480 | 11.198 | 2.29 |
| 0/23 | hc.a.gate | 3,686,400 | 21,120 | 25,600 | 25.417 | 145.87 |
| 0/23 | hc.a.low | 3,850,240 | 20,480 | 1,352 | 11.250 | 344.06 |
| 0/23 | hc.a.norm | 40,960 | 20,480 | 21,760 | 7.813 | 7.86 |
| 0/23 | hc.f.gate | 3,686,400 | 21,120 | 25,600 | 25.625 | 144.68 |
| 0/23 | hc.f.low | 3,850,240 | 20,480 | 1,352 | 11.666 | 331.79 |
| 0/23 | hc.f.norm | 40,960 | 20,480 | 21,760 | 7.812 | 7.86 |
| 0/23 | moe | 0 | 61,486 | 10,240 | 6.354 | 9.68 |
| 0/23 | qsa.attention | 0 | 263,048 | 86,596 | 44.479 | 5.91 |
| 0/23 | qsa.ik | 655,360 | 7,168 | 2,304 | 6.354 | 104.27 |
| 0/23 | qsa.iq | 2,621,440 | 5,120 | 1,024 | 9.062 | 289.83 |
| 0/23 | qsa.k | 1,638,400 | 5,120 | 1,024 | 8.437 | 194.80 |
| 0/23 | qsa.pool | 0 | 2,304 | 2,304 | 2.969 | 0.78 |
| 0/23 | qsa.prepare | 2,560 | 26,752 | 26,624 | 5.000 | 5.86 |
| 0/23 | qsa.qgate | 39,321,600 | 5,120 | 24,576 | 76.980 | 510.87 |
| 0/23 | qsa.select | 0 | 6,224 | 8,284 | 14.479 | 0.43 |
| 0/23 | qsa.v | 1,638,400 | 5,120 | 1,024 | 8.333 | 197.23 |
| 0/23 | route | 0 | 4,392 | 2,664 | 19.271 | 0.23 |
| 0/23 | router | 9,349,120 | 5,120 | 3,586 | 21.979 | 425.60 |
| 0/23 | shexpact | 0 | 2,560 | 1,280 | 4.531 | 0.56 |
| 0/23 | shexpdown | 1,843,200 | 1,280 | 5,120 | 10.989 | 167.84 |
| 1/24 | attention | 19,660,800 | 73,736 | 66,560 | 48.854 | 403.95 |
| 1/24 | expsact | 0 | 25,600 | 12,800 | 5.625 | 4.55 |
| 1/24 | expsdown | 9,216,000 | 12,920 | 51,240 | 57.708 | 159.92 |
| 1/24 | expsgate | 10,496,000 | 5,240 | 25,680 | 73.542 | 142.79 |
| 1/24 | ffn.combine | 0 | 25,608 | 20,480 | 11.042 | 2.32 |
| 1/24 | gdn.a | 983,040 | 5,120 | 192 | 6.875 | 143.73 |
| 1/24 | gdn.conv | 163,840 | 81,920 | 81,920 | 7.396 | 33.23 |
| 1/24 | gdn.gated | 512 | 24,576 | 12,288 | 5.625 | 4.46 |
| 1/24 | gdn.qkv | 32,768,000 | 5,120 | 20,480 | 63.750 | 514.09 |
| 1/24 | gdn.recurrence | 384 | 1,593,536 | 1,585,152 | 34.896 | 45.68 |
| 1/24 | gdn.z | 19,660,800 | 5,120 | 12,288 | 39.479 | 498.14 |
| 1/24 | hc.a.gate | 3,686,400 | 21,120 | 25,600 | 25.104 | 147.69 |
| 1/24 | hc.a.low | 3,850,240 | 20,480 | 1,352 | 11.771 | 328.84 |
| 1/24 | hc.a.norm | 40,960 | 20,480 | 21,760 | 9.843 | 6.24 |
| 1/24 | hc.f.gate | 3,686,400 | 21,120 | 25,600 | 24.583 | 150.82 |
| 1/24 | hc.f.low | 3,850,240 | 20,480 | 1,352 | 11.666 | 331.79 |
| 1/24 | hc.f.norm | 40,960 | 20,480 | 21,760 | 7.813 | 7.86 |
| 1/24 | moe | 0 | 61,486 | 10,240 | 6.458 | 9.52 |
| 1/24 | route | 0 | 4,392 | 2,664 | 20.052 | 0.22 |
| 1/24 | router | 9,349,120 | 5,120 | 3,586 | 22.188 | 421.59 |
| 1/24 | shexpact | 0 | 2,560 | 1,280 | 4.166 | 0.61 |
| 1/24 | shexpdown | 1,843,200 | 1,280 | 5,120 | 11.354 | 162.44 |
| 1/27 | attention | 19,660,800 | 73,736 | 66,560 | 47.291 | 417.30 |
| 1/27 | expsact | 0 | 25,600 | 12,800 | 5.729 | 4.47 |
| 1/27 | expsdown | 9,216,000 | 12,920 | 51,240 | 57.813 | 159.63 |
| 1/27 | expsgate | 10,496,000 | 5,240 | 25,680 | 73.021 | 143.81 |
| 1/27 | ffn.combine | 0 | 25,608 | 20,480 | 11.042 | 2.32 |
| 1/27 | hc.a.gate | 3,686,400 | 21,120 | 25,600 | 24.480 | 151.45 |
| 1/27 | hc.a.low | 3,850,240 | 20,480 | 1,352 | 11.355 | 340.88 |
| 1/27 | hc.a.norm | 40,960 | 20,480 | 21,760 | 7.709 | 7.97 |
| 1/27 | hc.f.gate | 3,686,400 | 21,120 | 25,600 | 25.521 | 145.27 |
| 1/27 | hc.f.low | 3,850,240 | 20,480 | 1,352 | 11.511 | 336.28 |
| 1/27 | hc.f.norm | 40,960 | 20,480 | 21,760 | 7.812 | 7.86 |
| 1/27 | moe | 0 | 61,486 | 10,240 | 6.355 | 9.68 |
| 1/27 | qsa.attention | 0 | 263,048 | 86,596 | 44.843 | 5.87 |
| 1/27 | qsa.ik | 655,360 | 7,168 | 2,304 | 6.458 | 102.60 |
| 1/27 | qsa.iq | 2,621,440 | 5,120 | 1,024 | 9.166 | 286.55 |
| 1/27 | qsa.k | 1,638,400 | 5,120 | 1,024 | 8.646 | 190.09 |
| 1/27 | qsa.pool | 0 | 2,304 | 2,304 | 3.333 | 0.69 |
| 1/27 | qsa.prepare | 2,560 | 26,752 | 26,624 | 5.208 | 5.63 |
| 1/27 | qsa.qgate | 39,321,600 | 5,120 | 24,576 | 77.396 | 508.12 |
| 1/27 | qsa.select | 0 | 6,224 | 8,284 | 14.375 | 0.43 |
| 1/27 | qsa.v | 1,638,400 | 5,120 | 1,024 | 8.437 | 194.80 |
| 1/27 | route | 0 | 4,392 | 2,664 | 19.583 | 0.22 |
| 1/27 | router | 9,349,120 | 5,120 | 3,586 | 21.562 | 433.82 |
| 1/27 | shexpact | 0 | 2,560 | 1,280 | 4.167 | 0.61 |
| 1/27 | shexpdown | 1,843,200 | 1,280 | 5,120 | 10.938 | 168.63 |

## Selection

QKV, Z and Q-gate fail the0.3 ms threshold and get no candidate. Attention output qualifies on rank1 only, narrowly, when the GDN and QSA occurrences of the same output kernel are combined. Its two event stages must be summed: the roughly23 us mixed-event median is not a call time. The proposed class is all attention outputs, with a shared Q6_K6144 Split4 arithmetic body; neither subtype alone qualifies.

HC gates, recurrence and route numerically qualify. Packet67 already tested the HC/recurrence geometry changes and lost on every arm; this table supplies no new device counter evidence to reopen those mechanisms. Route has no raw packed code/scale loop to which wide64 applies. Experts are already wide64 in packet70; packet64 expert times are historical, not packet70 times. Those classes get no speculative replacement here.

Only attention-output raw-code/scale sharing proceeds. It retains the original Split4 scratch and final stream-combine kernel. The combined view equals this sole qualifying new mechanism; the production control is packet70 including wide64 experts, batch rollback and draft-HC.

Outside-layer time cannot be assigned bandwidth from these events: target head/final norm/argmax lack separate site timings here. Packet69 owns that attribution. All unsampled times and actual DRAM bandwidth stay null.

[JSON with event hashes and formulas](BANDWIDTH.json), [all-layer tensor inventory](all-layer-bytes.json), [header pins](header-census.json), [CPU reproducer](bandwidth.py).
