# Packet73 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet70's slow in-engine HC and expert sites issue raw loads more
successfully without changing the quantized compressed model's arithmetic?
The target is Unsloth Flash-Next UD-IQ3_XXS, full BF16 KV,
`iq3-p49-split32-v1`, the packet70 draft-HC/batch/24–24 preset and wide64 experts.
Preparation on steve-b70s was CPU-only on October 17, 2026. GPU screens belong
to the coordinator. This closes preparation, not the optimization lane.

## Outcome

Five views share one sealed engine binary. All 44 operator cases pass twice
under GNU and twice under Intel, with 118,784 raw FP32 chain checks and 3,456
raw tree checks per run. All accepted HC/expert kernels have 128 configured
GRFs and no spill metadata or spill/fill messages. The private v4 wrapper passes
82 mock checks. Six A plans and all twelve possible B plans pass; both queue
proposals pass a temporary-copy lanequeue plan. No device speed is measured.
Build size is 302,710,656 bytes; engine compiler peak RSS is 726,108 KiB.

## What worked

HC shares raw inputs across two adjacent output rows while preserving original
32-lane reductions. IQ2 issues two packed spans before consumption. IQ4 shares
two blocks' codes/scales and reduces static load instructions 79 to 43.
Matched CPU byte gates rejected a wrong stride before it could reach a screen.
The offline compiler now links the SYCL math libraries before counting spills.

## What failed or remains uncertain

HC virtual-four-chain layouts spilled flags and were rejected. A larger IQ4
span spilled GRFs; the smaller span passed. Unlinked math calls distorted the
first HC offline reports. Route fusion was deferred because of normalization
and synchronization requirements. Actual occupancy, DRAM traffic, full-model
exactness and speed are unmeasured. Deeper IQ2 issue is a hypothesis despite
its clean offline spill check. No source count is a performance result.

## Evidence and patches

- [Offline decisions and raw report links](OCCUPANCY.md)
- [CPU byte receipt](evidence/cpu-byte-identity.json)
- [Final verification](evidence/final-validation.json)
- [Five view seals](selections/production/screen-seal.json), same binary hash
- [Private v4 test log](screen/placement-validation/tests.log)
- [A plans](evidence/plans-A.json), [all B plans](evidence/plans-B.json), [queue plans](evidence/queue-plans.json)
- [Negative index](DO-NOT-REPEAT.md), [rejected artifact map](evidence/rejected-artifact-map.json)
- [Source and build retention/restoration](RETENTION.md)

No external source patch or technique was adopted in this packet.

## When to revisit

The coordinator runs [A then B](WINDOW.md) with current admission and fault
review. Keep only an exact candidate that improves against both same-lane
control sandwiches. Device evidence determines the next lever; a screen win
still requires separate record qualification before promotion.
