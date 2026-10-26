# Rank-0 lab driver and exact draft optimizations (2026-10-26)

## Driver

`tp_rank0_driver.py` drives one rank-0 engine without rank 1 or the native controller. It supplies deterministic token
ids and reverse hidden rows, performs batched prefill and draft replay, then alternating target HALF/ACCEPT and draft
steps. RESET dumps both target and draft state. `compare` requires identical target buffers, draft allocations and
published guesses. The driver used the live B17 environment, split 23, context 65536 and 256-row prefill chunks.
Every device run held only renderD131 (card 27) under `flock /dev/shm/card27.lock`; before/after kernel-fault checks
were clean.

## Accepted candidate

Enable all four default-off switches:

- `OWNRT_DRAFT_HEAD_RAW=1`: raw-size Q6_K draft-head prefix, with the existing load-time element comparison.
- `OWNRT_DRAFT_ATTN=1`: BF16 query-head-shared QSA tiles and blocked combine.
- `OWNRT_DRAFT_EXPERTS_V2=1`: packed FP8 code/scale/input loads; per-output operation order is unchanged.
- `OWNRT_DRAFT_MERGE=1`: one weight traversal for the four draft hidden-merge streams; each output keeps its own
  accumulation and reduction order.

The reference was the live B17 binary (`96473c90783c`). The candidate was built from B17 canonical source plus
`rank0-draft.patch`; switch-off runs on that binary matched the reference.

## Final 4096-row gate

| Run | Prompt ms | Draft replay ms | Target-half median ms | Draft median ms |
|---|---:|---:|---:|---:|
| B17 reference | 18250 | 6023 | 10.786 | 2.188 |
| all four switches | 17297 | 5076 | 10.731 | 1.731 |
| candidate binary, switches off | 18220 | 6028 | 10.796 | 2.198 |

Both comparisons passed with `compared=1029`, `differ_count=0`, `only_one_side=[]`, no other differing fields,
`draft_compared=71`, `draft_differ_count=0`, no draft allocation on only one side, and `draft_tokens_equal=true`.
The earlier 300-row gate passed the same checks. The raw-head receipt checked 233,963,520 elements with zero
mismatches (91,392 rows; 191,923,200 raw bytes instead of 308,904,960 expanded bytes).

Three earlier interleaved rounds measured draft 2.195/2.193/2.186 ms off versus 1.731/1.735/1.726 ms on; target-half
10.791/10.784/10.783 versus 10.717/10.732/10.723 ms. The isolated raw-head switch measured draft 2.190/2.191/2.190
off versus 2.005/2.009/2.005 on, with no material target-half change.

## CPU-device tests

With GPU access blocked, the OpenCL CPU tests compared against replicas of the incumbent arithmetic:

- `test_draft_attention`: 22/22 cases, including slot counts 1–2051, multiple rows, ties and repeated ids;
  output, partials, errors and sentinel tails all passed.
- `test_draft_fp8`: gate/up and down, paired and unpaired, valid/partial/invalid routes; all outputs and status words
  matched.
- `test_draft_merge`: `merge_add` and no-tail forms; all 20,480 outputs in each case matched.

## Scope

B18 (`728c70b3eec6`) passed both context oracles with zero differences, prefill 13/13, long/short continuation and
prior-build session compatibility. Its cold 12-prompt suite matched B17 in every output id/hash and all MTP hits;
median decode rose from 64.005 to 65.669 tok/s (+2.60%). Hosting was then stopped by the owner's choice so all four
cards could run independent optimization lanes.
## Rejected follow-up: attention-output split scheduling

`OWNRT_DRAFT_ATTN_OUT` was a lab-only attempt to execute the existing four attention-output partitions sequentially in
one subgroup, retaining their lane and partition reduction order. The small OpenCL CPU test passed all 201 outputs and
sentinel bytes, but the real 4096-row card-27 gate differed in `card0:draft:blk.0.attention` (one of 71 draft buffers;
all 1,029 target buffers and all tokens still matched). Unprofiled timing was neutral (draft 1.727 ms off versus
1.726 ms on). The variant is rejected and is not in canonical `engine/src` or B18. Do not promote it based on the CPU
test or token equality.
