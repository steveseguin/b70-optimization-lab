# Exploratory runs (not certified, not preregistered)

Quick feasibility probes with the pinned llama.cpp SYCL reference build. They
inform planning only; the lane's numbers come from the preregistered screens.

| Date (UTC) | Run | Cards | Result | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-11 02:30 | `onecard-fit-20261011-attempt1-nofit` | 1 (card 2) | aborted by coordinator after 10 min | `--gpu-layers all` disabled the fitter ("already set by user"), so it tried to load everything on one card |
| 2026-10-11 02:45 | `onecard-fit-20261011b` | 1 (card 2) | **decode 21.64 tok/s**, prompt 49.8 tok/s, 63 tokens, rc 0, 0 kernel fault lines | `--fit on` chose the split itself (some tensors overridden to CPU, mmap); quiet log, so the exact layer split is not recorded; output text differs from the two-card run after the first sentence (different split, different arithmetic order; the CPU oracle is the authority) |

Context: the concurrent two-card preregistered baseline on cards 0-1 measured
25.9-26.9 tok/s decode on the same prompts. Owner targets (2026-10-11): two
B70s primary, one B70 secondary; parallel runs on disjoint cards allowed.
