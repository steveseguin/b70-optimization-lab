# The speculative tree stack is built, tested, and unwired

Date: 2026-08-05 America/Toronto

> **CHECKED, and it is blocked too.** The tree needs the drafter's rank-2
> candidate at branching positions. **DFlash emits top-1 only**: its reduction
> is `local_argmax`, and the M8 breakable-graph contract independently requires
> `draft_sample_method == "greedy"`. So wiring it needs a new top-2 reduction on
> the drafter path plus a contract change, not plumbing.
>
> The **+3.3% is also an upper bound**, by the spec module's own admission: a
> node whose ancestry departs from the top-1 spine "is drafted from a
> distribution that assumed the spine, so its acceptance is lower than its depth
> and rank alone imply." The realised gain is smaller than 3.3%.
>
> **Verdict: not worth it.** Sub-3% for a drafter-side kernel change and a
> contract relaxation in the exactness-critical path. Recorded so the next
> person does not rediscover the stack and assume it is ready to switch on.

Status: **the last candidate lever, examined and declined on cost. 240 tests
pass; nothing calls it; and the piece it depends on does not exist.**

## What exists

Three modules in the vLLM fork, 504 lines, mutually consistent:

| module | lines | role |
| :--- | ---: | :--- |
| `laguna_tree_spec.py` | 221 | topology: `build_greedy_tree`, `build_chain` |
| `laguna_tree_metadata.py` | 159 | per-row attention plan and private block tables |
| `laguna_tree_accept.py` | 124 | walks the tree and emits the accepted prefix |

**Nothing in the serving path imports any of them**, and there is no
`VLLM_XPU_LAGUNA_*TREE*` selector anywhere. `laguna_tree_spec` is imported only
by the other two.

## It is tested, including exactness

```
tests/v1/spec_decode/test_laguna_tree_spec.py
tests/v1/spec_decode/test_laguna_tree_metadata.py       100 passed
tests/v1/spec_decode/test_laguna_tree_accept.py
tests/v1/spec_decode/test_laguna_tree_end_to_end.py     140 passed
```

The end-to-end test composes all three on CPU -- topology, verifier metadata, a
simulated target reading each row through its own block table, then acceptance
-- and asserts the pipeline emits the target's greedy continuation. Its
docstring is explicit that the simulated target reads a row's *actual* attended
context, so "a metadata bug that let a row see a sibling's token would change
its prediction and fail the exactness assertion rather than passing silently."

That is the property the whole campaign is built on, and it is already covered.

## What it is worth

Scored on the module's own measured rank probabilities (0.756 rank-1, +0.126
for rank 2, over 2,131 record-configuration cycles):

| width | chain | greedy tree | gain |
| ---: | ---: | ---: | ---: |
| **12 (today)** | 3.956 | **4.084** | **+3.3%** |

**+3.3% tokens per step for zero extra verifier rows**, hence no cycle-time
increase -- unlike widening, which the 2026-07-26 measurement priced at +14.61%
cycle time for +0.21% tokens and which is a net loss even with an optimal tree.

At the measured 162.0 tok/s that is about **167 tok/s**, quality-neutral.

## What it costs in memory

Each tree row needs private KV blocks so it attends only to its ancestors:
`private_blocks_per_row = ceil((block_size - 1 + max_depth) / block_size)`,
which at block size 64 and the greedy tree's depth 8 is **2 blocks**.

| quantity | value |
| :--- | ---: |
| private blocks per row | 2 |
| draft rows | 11 |
| extra KV per rank | **66 MiB** |
| share of the 2.89 GiB KV budget | **2.2%** |

Negligible, which matters because memory is the binding constraint on this
machine -- it is what blocked replicated attention.

## What wiring requires

1. An env selector, default off, in the harness `common_env` -- **not** on the
   command line, because the runner launches under `env -i`.
2. Build the spec once at init with `build_greedy_tree(M - 1)`.
3. Allocate the 11x2 private blocks and call `build_tree_verifier_plan`.
4. Have the drafter emit **rank-2** candidates at branching positions; the tree
   assumes top-2 are available, and today's chain only needs top-1. **This is
   the one piece whose availability is unverified.**
5. Replace chain rejection with `accept_tree`.
6. Verify the token stream against canonical `154c7d6e19b3`, and confirm the
   captured topology is unchanged at 146/145 -- the row count does not move, so
   it should be.

Step 4 is the risk. Everything else is plumbing over tested code.

## Why it is the last one

Every other lever is measured and closed
([ledger](2026-08-05-FINAL-every-decode-lever-is-now-measured.md)): collective
count is blocked on +3 GiB/rank, MoE compute is the model, bytes are at 69% of
PCIe, depth's tail is spent by 11, graph breaks broke 32K exactness, and width
is a net loss. This is what remains.

It does not reach 250 -- nothing does on this hardware. It is worth doing
because it is real, cheap, quality-neutral, and already written.

## Boundaries

Test counts are from runs in the `deepseek-v4-xpu` venv on this tree at commit
`68a4965de`. Tree scores are exact arithmetic on the module's own constants,
not simulations or measurements of a served model. The memory figure is
arithmetic on the module's own block formula. No quantisation change. The
protected `125.4619731637751 tok/s` conventional short-decode record is
untouched.
