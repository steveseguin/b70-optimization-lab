# Packet67 roofline audit

CPU header/source accounting against the October 17 lane-B packet64 attribution. No model payload or device was read. **These are useful-byte lower bounds, not measured DRAM traffic or achievable speedups.** Exact HBM bytes require device counters; cached duplicate loads, codebooks, control words and line overfetch are not measurable from these receipts.

The model headers match all 1224 tensors in the admitted census. [Header identities](header-census.json), [reproducer](audit.py), [full counts/formulas and raw event hashes](roofline.json).

Q6_K/Q8_0 dense matrices run as expanded codes plus F32 scales. Count K+K/4 and K+K/8 bytes per row respectively; preserved packed metadata in the allocation is not loaded by these kernels. Routed IQ2_S/IQ3_S/IQ4_NL remain compact. The filename is not a tensor type.

540 GB/s is the requested practical mixed-traffic reference. [Earlier copy evidence](../../../../notes/2026-10-15-p45-roofline-and-structural-levers.md) reports 528–545 GB/s read+write, and 589–601 GB/s streaming read. Use (reads+writes)/540000 for microseconds, not a copy-payload denominator. Compute/reduction/decode floors remain unmeasured.

**Timing correction:** sum all events per (prompt, rank, fixture, label) before taking a median. `attention` has two kernels, `route` four, `moe` two, and QSA attention three. The brief’s ~23 us attention median mixes the ~41 us producer and ~5 us finish; its complete call costs roughly twice that. No scaled control/instrumented estimates are used here.

## Ranked per-half excess (common sites combine 18 GDN and 6 QSA occurrences)

| Rank | Site | Call time × occurrences, µs | Excess over memory floor, µs/half |
| ---: | --- | ---: | ---: |
| 0 | expsgate | 1747.81 | 1279.95 |
| 0 | expsdown | 1367.50 | 955.04 |
| 0 | gdn.recurrence | 644.99 | 539.02 |
| 0 | route | 464.39 | 464.08 |
| 0 | hc.f.gate | 600.01 | 434.09 |
| 0 | hc.a.gate | 598.76 | 432.84 |
| 0 | ffn.combine | 265.94 | 263.90 |
| 0 | qsa.attention | 266.87 | 262.99 |
| 0 | attention | 1113.44 | 233.39 |
| 0 | hc.a.norm | 186.57 | 182.87 |
| 0 | shexpdown | 262.81 | 180.61 |
| 0 | hc.f.norm | 183.74 | 180.05 |
| 0 | moe | 148.75 | 145.56 |
| 0 | expsact | 135.31 | 133.61 |
| 0 | hc.f.low | 305.31 | 133.22 |
| 0 | gdn.conv | 131.26 | 120.33 |
| 0 | router | 530.31 | 114.41 |
| 0 | shexpact | 100.32 | 100.15 |
| 0 | gdn.gated | 99.38 | 98.13 |
| 0 | hc.a.low | 270.00 | 97.91 |
| 0 | gdn.a | 120.00 | 87.05 |
| 0 | qsa.select | 86.87 | 86.71 |
| 0 | gdn.qkv | 1178.44 | 85.32 |
| 0 | gdn.z | 706.88 | 50.94 |
| 0 | qsa.k | 50.62 | 32.35 |
| 0 | qsa.v | 50.00 | 31.73 |
| 0 | qsa.ik | 38.12 | 30.74 |
| 0 | qsa.prepare | 30.00 | 29.38 |
| 0 | qsa.iq | 54.38 | 25.18 |
| 0 | qsa.qgate | 461.88 | 24.64 |
| 0 | qsa.pool | 17.81 | 17.76 |
| 1 | expsgate | 1761.88 | 1294.02 |
| 1 | expsdown | 1385.62 | 973.17 |
| 1 | gdn.recurrence | 628.13 | 522.16 |
| 1 | route | 478.43 | 478.12 |
| 1 | hc.a.gate | 598.75 | 432.84 |
| 1 | hc.f.gate | 595.62 | 429.70 |
| 1 | attention | 1163.12 | 283.07 |
| 1 | qsa.attention | 269.06 | 265.18 |
| 1 | ffn.combine | 265.01 | 262.96 |
| 1 | hc.a.norm | 223.44 | 219.74 |
| 1 | shexpdown | 270.01 | 187.80 |
| 1 | hc.f.norm | 187.51 | 183.81 |
| 1 | moe | 154.37 | 151.19 |
| 1 | expsact | 135.62 | 133.92 |
| 1 | gdn.conv | 133.13 | 122.21 |
| 1 | router | 528.76 | 112.86 |
| 1 | hc.a.low | 280.01 | 107.92 |
| 1 | hc.f.low | 279.05 | 106.96 |
| 1 | gdn.gated | 101.25 | 100.00 |
| 1 | shexpact | 99.99 | 99.82 |
| 1 | gdn.a | 123.75 | 90.80 |
| 1 | qsa.select | 86.25 | 86.09 |
| 1 | gdn.z | 710.62 | 54.68 |
| 1 | gdn.qkv | 1147.50 | 54.38 |
| 1 | qsa.k | 51.88 | 33.60 |
| 1 | qsa.v | 50.62 | 32.35 |
| 1 | qsa.ik | 38.75 | 31.36 |
| 1 | qsa.prepare | 31.25 | 30.63 |
| 1 | qsa.qgate | 464.38 | 27.14 |
| 1 | qsa.iq | 55.00 | 25.80 |
| 1 | qsa.pool | 20.00 | 19.95 |

## Every sampled per-layer site

Times are medians of complete non-speculative calls; rank0 has miss-only samples. Read/write columns count decimal bytes. Occurrences are 18 GDN or 6 QSA per half, an estimate from sampled layers. Full names, dimensions, storage types, context ranges and stage counts are in JSON.

| Rank/layer | Site | GGUF weights B | Runtime read B | Write B | µs/call | GB/s | Excess µs/half |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0/22 | attention | 12,902,400.0 | 19,734,536 | 66,560 | 46.511 | 425.7 | 177.15 |
| 0/22 | expsact | 0.0 | 25,600 | 12,800 | 5.677 | 6.8 | 100.91 |
| 0/22 | expsdown | 9,216,000.0 | 9,228,920 | 51,240 | 56.979 | 162.9 | 716.28 |
| 0/22 | expsgate | 10,496,000.0 | 10,501,240 | 25,680 | 72.864 | 144.5 | 960.66 |
| 0/22 | ffn.combine | 0.0 | 25,608 | 20,480 | 11.042 | 4.2 | 197.22 |
| 0/22 | gdn.a | 983,040.0 | 988,160 | 192 | 6.667 | 148.3 | 87.05 |
| 0/22 | gdn.conv | 163,840.0 | 245,760 | 81,920 | 7.292 | 44.9 | 120.33 |
| 0/22 | gdn.gated | 512.0 | 25,088 | 12,288 | 5.521 | 6.8 | 98.13 |
| 0/22 | gdn.qkv | 21,504,000.0 | 32,773,120 | 20,480 | 65.469 | 500.9 | 85.32 |
| 0/22 | gdn.recurrence | 384.0 | 1,593,920 | 1,585,152 | 35.833 | 88.7 | 539.02 |
| 0/22 | gdn.z | 12,902,400.0 | 19,665,920 | 12,288 | 39.271 | 501.1 | 50.94 |
| 0/22 | hc.a.gate | 3,481,600.0 | 3,707,520 | 25,600 | 24.792 | 150.6 | 321.82 |
| 0/22 | hc.a.low | 3,645,440.0 | 3,870,720 | 1,352 | 11.250 | 344.2 | 73.43 |
| 0/22 | hc.a.norm | 40,960.0 | 61,440 | 21,760 | 7.761 | 10.7 | 136.92 |
| 0/22 | hc.f.gate | 3,481,600.0 | 3,707,520 | 25,600 | 24.792 | 150.6 | 321.82 |
| 0/22 | hc.f.low | 3,645,440.0 | 3,870,720 | 1,352 | 13.073 | 296.2 | 106.24 |
| 0/22 | hc.f.norm | 40,960.0 | 61,440 | 21,760 | 7.604 | 10.9 | 134.10 |
| 0/22 | moe | 0.0 | 61,486 | 10,240 | 6.146 | 11.7 | 108.24 |
| 0/22 | route | 0.0 | 4,392 | 2,664 | 19.376 | 0.4 | 348.53 |
| 0/22 | router | 7,941,120.0 | 9,354,240 | 3,586 | 22.136 | 422.8 | 86.51 |
| 0/22 | shexpact | 0.0 | 2,560 | 1,280 | 4.063 | 0.9 | 73.01 |
| 0/22 | shexpdown | 1,740,800.0 | 1,844,480 | 5,120 | 10.938 | 169.1 | 135.22 |
| 0/23 | attention | 12,902,400.0 | 19,734,536 | 66,560 | 46.042 | 430.1 | 56.24 |
| 0/23 | expsact | 0.0 | 25,600 | 12,800 | 5.521 | 7.0 | 32.70 |
| 0/23 | expsdown | 9,216,000.0 | 9,228,920 | 51,240 | 56.979 | 162.9 | 238.76 |
| 0/23 | expsgate | 10,496,000.0 | 10,501,240 | 25,680 | 72.708 | 144.8 | 319.28 |
| 0/23 | ffn.combine | 0.0 | 25,608 | 20,480 | 11.198 | 4.1 | 66.68 |
| 0/23 | hc.a.gate | 3,481,600.0 | 3,707,520 | 25,600 | 25.417 | 146.9 | 111.02 |
| 0/23 | hc.a.low | 3,645,440.0 | 3,870,720 | 1,352 | 11.250 | 344.2 | 24.48 |
| 0/23 | hc.a.norm | 40,960.0 | 61,440 | 21,760 | 7.813 | 10.6 | 45.95 |
| 0/23 | hc.f.gate | 3,481,600.0 | 3,707,520 | 25,600 | 25.625 | 145.7 | 112.27 |
| 0/23 | hc.f.low | 3,645,440.0 | 3,870,720 | 1,352 | 11.666 | 331.9 | 26.97 |
| 0/23 | hc.f.norm | 40,960.0 | 61,440 | 21,760 | 7.812 | 10.7 | 45.95 |
| 0/23 | moe | 0.0 | 61,486 | 10,240 | 6.354 | 11.3 | 37.33 |
| 0/23 | qsa.attention | 0.0 | 263,048 | 86,596 | 44.479 | 7.9 | 262.99 |
| 0/23 | qsa.ik | 655,360.0 | 662,528 | 2,304 | 6.354 | 104.6 | 30.74 |
| 0/23 | qsa.iq | 2,621,440.0 | 2,626,560 | 1,024 | 9.062 | 289.9 | 25.18 |
| 0/23 | qsa.k | 1,075,200.0 | 1,643,520 | 1,024 | 8.437 | 194.9 | 32.35 |
| 0/23 | qsa.pool | 0.0 | 2,304 | 2,304 | 2.969 | 1.6 | 17.76 |
| 0/23 | qsa.prepare | 2,560.0 | 29,312 | 26,624 | 5.000 | 11.2 | 29.38 |
| 0/23 | qsa.qgate | 25,804,800.0 | 39,326,720 | 24,576 | 76.980 | 511.2 | 24.64 |
| 0/23 | qsa.select | 0.0 | 6,224 | 8,284 | 14.479 | 1.0 | 86.71 |
| 0/23 | qsa.v | 1,075,200.0 | 1,643,520 | 1,024 | 8.333 | 197.4 | 31.73 |
| 0/23 | route | 0.0 | 4,392 | 2,664 | 19.271 | 0.4 | 115.55 |
| 0/23 | router | 7,941,120.0 | 9,354,240 | 3,586 | 21.979 | 425.8 | 27.90 |
| 0/23 | shexpact | 0.0 | 2,560 | 1,280 | 4.531 | 0.8 | 27.14 |
| 0/23 | shexpdown | 1,740,800.0 | 1,844,480 | 5,120 | 10.989 | 168.3 | 45.39 |
| 1/24 | attention | 12,902,400.0 | 19,734,536 | 66,560 | 48.854 | 405.3 | 219.34 |
| 1/24 | expsact | 0.0 | 25,600 | 12,800 | 5.625 | 6.8 | 99.97 |
| 1/24 | expsdown | 9,216,000.0 | 9,228,920 | 51,240 | 57.708 | 160.8 | 729.41 |
| 1/24 | expsgate | 10,496,000.0 | 10,501,240 | 25,680 | 73.542 | 143.1 | 972.86 |
| 1/24 | ffn.combine | 0.0 | 25,608 | 20,480 | 11.042 | 4.2 | 197.22 |
| 1/24 | gdn.a | 983,040.0 | 988,160 | 192 | 6.875 | 143.8 | 90.80 |
| 1/24 | gdn.conv | 163,840.0 | 245,760 | 81,920 | 7.396 | 44.3 | 122.21 |
| 1/24 | gdn.gated | 512.0 | 25,088 | 12,288 | 5.625 | 6.6 | 100.00 |
| 1/24 | gdn.qkv | 21,504,000.0 | 32,773,120 | 20,480 | 63.750 | 514.4 | 54.38 |
| 1/24 | gdn.recurrence | 384.0 | 1,593,920 | 1,585,152 | 34.896 | 91.1 | 522.16 |
| 1/24 | gdn.z | 12,902,400.0 | 19,665,920 | 12,288 | 39.479 | 498.4 | 54.68 |
| 1/24 | hc.a.gate | 3,481,600.0 | 3,707,520 | 25,600 | 25.104 | 148.7 | 327.43 |
| 1/24 | hc.a.low | 3,645,440.0 | 3,870,720 | 1,352 | 11.771 | 329.0 | 82.81 |
| 1/24 | hc.a.norm | 40,960.0 | 61,440 | 21,760 | 9.843 | 8.5 | 174.41 |
| 1/24 | hc.f.gate | 3,481,600.0 | 3,707,520 | 25,600 | 24.583 | 151.9 | 318.06 |
| 1/24 | hc.f.low | 3,645,440.0 | 3,870,720 | 1,352 | 11.666 | 331.9 | 80.92 |
| 1/24 | hc.f.norm | 40,960.0 | 61,440 | 21,760 | 7.813 | 10.6 | 137.86 |
| 1/24 | moe | 0.0 | 61,486 | 10,240 | 6.458 | 11.1 | 113.85 |
| 1/24 | route | 0.0 | 4,392 | 2,664 | 20.052 | 0.4 | 360.70 |
| 1/24 | router | 7,941,120.0 | 9,354,240 | 3,586 | 22.188 | 421.8 | 87.46 |
| 1/24 | shexpact | 0.0 | 2,560 | 1,280 | 4.166 | 0.9 | 74.86 |
| 1/24 | shexpdown | 1,740,800.0 | 1,844,480 | 5,120 | 11.354 | 162.9 | 142.73 |
| 1/27 | attention | 12,902,400.0 | 19,734,536 | 66,560 | 47.291 | 418.7 | 63.73 |
| 1/27 | expsact | 0.0 | 25,600 | 12,800 | 5.729 | 6.7 | 33.95 |
| 1/27 | expsdown | 9,216,000.0 | 9,228,920 | 51,240 | 57.813 | 160.5 | 243.77 |
| 1/27 | expsgate | 10,496,000.0 | 10,501,240 | 25,680 | 73.021 | 144.2 | 321.16 |
| 1/27 | ffn.combine | 0.0 | 25,608 | 20,480 | 11.042 | 4.2 | 65.74 |
| 1/27 | hc.a.gate | 3,481,600.0 | 3,707,520 | 25,600 | 24.480 | 152.5 | 105.40 |
| 1/27 | hc.a.low | 3,645,440.0 | 3,870,720 | 1,352 | 11.355 | 341.0 | 25.11 |
| 1/27 | hc.a.norm | 40,960.0 | 61,440 | 21,760 | 7.709 | 10.8 | 45.33 |
| 1/27 | hc.f.gate | 3,481,600.0 | 3,707,520 | 25,600 | 25.521 | 146.3 | 111.65 |
| 1/27 | hc.f.low | 3,645,440.0 | 3,870,720 | 1,352 | 11.511 | 336.4 | 26.04 |
| 1/27 | hc.f.norm | 40,960.0 | 61,440 | 21,760 | 7.812 | 10.7 | 45.95 |
| 1/27 | moe | 0.0 | 61,486 | 10,240 | 6.355 | 11.3 | 37.33 |
| 1/27 | qsa.attention | 0.0 | 263,048 | 86,596 | 44.843 | 7.8 | 265.18 |
| 1/27 | qsa.ik | 655,360.0 | 662,528 | 2,304 | 6.458 | 103.0 | 31.36 |
| 1/27 | qsa.iq | 2,621,440.0 | 2,626,560 | 1,024 | 9.166 | 286.7 | 25.80 |
| 1/27 | qsa.k | 1,075,200.0 | 1,643,520 | 1,024 | 8.646 | 190.2 | 33.60 |
| 1/27 | qsa.pool | 0.0 | 2,304 | 2,304 | 3.333 | 1.4 | 19.95 |
| 1/27 | qsa.prepare | 2,560.0 | 29,312 | 26,624 | 5.208 | 10.7 | 30.63 |
| 1/27 | qsa.qgate | 25,804,800.0 | 39,326,720 | 24,576 | 77.396 | 508.4 | 27.14 |
| 1/27 | qsa.select | 0.0 | 6,224 | 8,284 | 14.375 | 1.0 | 86.09 |
| 1/27 | qsa.v | 1,075,200.0 | 1,643,520 | 1,024 | 8.437 | 194.9 | 32.35 |
| 1/27 | route | 0.0 | 4,392 | 2,664 | 19.583 | 0.4 | 117.42 |
| 1/27 | router | 7,941,120.0 | 9,354,240 | 3,586 | 21.562 | 434.0 | 25.40 |
| 1/27 | shexpact | 0.0 | 2,560 | 1,280 | 4.167 | 0.9 | 24.96 |
| 1/27 | shexpdown | 1,740,800.0 | 1,844,480 | 5,120 | 10.938 | 169.1 | 45.08 |

## Outside the sampled repeated layers, each rank

Target head/final HC, embedding, singleton PLE, begin/commit and rollback copies have **no individual event times in this attribution**. They cannot have a defensible measured GB/s or ranked excess. The measured outside-layer means are 2346.34 µs rank0 speculative, 1102.49 µs rank0 corrected, and 3080.80 µs rank1 target. These mix host command overhead, copies and kernels; they are not GPU-idle measurements. Do not divide a partial byte inventory by that aggregate and call it kernel bandwidth.

| Rank | Work (once unless stated) | Read B | Write B | 540 GB/s floor µs |
| ---: | --- | ---: | ---: | ---: |
| 0 | embedding lookup | 2,100 | 5,120 | not applicable |
| 0 | streams broadcast | 5,120 | 20,480 | 0.047 |
| 0 | speculative capture | 48,627,432 | 48,627,432 | 180.102 |
| 0 | corrected redo restore | 19,025,640 | 19,025,640 | 70.465 |
| 0 | PLE lookup | 1,440 | 5,120 | not applicable |
| 0 | PLE key | 29,496,320 | 20,480 | 54.661 |
| 0 | PLE value | 7,377,920 | 5,120 | 13.672 |
| 0 | PLE three norms | 188,160 | 65,280 | 0.469 |
| 0 | PLE convolution | 368,640 | 204,800 | 1.062 |
| 0 | PLE gate and add | 107,520 | 40,960 | 0.275 |
| 0 | PLE hash/history | 300 | 144 | not applicable |
| 1 | final norm | 62,720 | 21,760 | 0.156 |
| 1 | final low + activation | 3,706,880 | 1,280 | 6.867 |
| 1 | final gate | 3,687,040 | 20,480 | 6.866 |
| 1 | final mix | 40,960 | 5,120 | 0.085 |
| 1 | target logits | 794,629,120 | 496,640 | 1472.455 |
| 1 | target argmax | 499,070 | 1,948 | 0.928 |
| 1 | rank handoff | 20,484 | 20,484 | not applicable |

The full target head is Q6_K, 794.624 MB useful expanded weights; its 1472 µs memory floor explains a large part of rank1’s outside-layer cost but is **not its measured time**. Snapshot sizes use retained per-capture/per-restore telemetry, not allocated capacity. PLE belongs to layer1 but is listed here because multiplying the sampled layers misses it. Small control/status work and host polling have no useful memory roofline; timing unavailable.

Draft work runs as a separate rank1 D command, not once inside each target half. Its measured class costs are retained in JSON separately; the draft head alone has 91392 rows (292454400 expanded Q6 bytes + 182784 output bytes + 5120 input bytes, about 541.93 µs at540). Its event median is not a target-head measurement. `mtp.hpp` gives 535119872 useful weight bytes per proposal: 292454400 head, 102891520 QSA/indexer BF16, 61440000 selected expert INT8 codes/F32 scales, 39485440 HC BF16, 12456960 router/shared BF16, 26214400 merge BF16 and 177152 F32 gains. These are separate official-sidecar draft formats; target GGUF types cannot be applied to that work. Draft activation/state traffic is not fully inventoried here and no complete draft bandwidth is claimed.

## Candidate decision

Experts remain packet65-owned. Of the remaining sites, choose recurrence and both HC gates. Route is also high after correcting the four-stage timing, but packet54 already changed rank scheduling and normalized-value reuse; it needs a separate mechanism study. Dense QKV, Q-gate and Z are near this useful-byte floor. The planned HC change targets the fused gate/mix geometry, which differs from the closed standalone HC virtualization arm. Recurrence targets repeated head normalization, not the already-register-resident state. No expected saving is a device result.
