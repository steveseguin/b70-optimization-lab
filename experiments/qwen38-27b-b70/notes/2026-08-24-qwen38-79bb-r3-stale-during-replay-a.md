# 79bb r3: clean arms stopped stale when vLLM main advanced

Date: 2026-08-24. Status: **closed failed-incomplete/stale after the fresh
diagnostic and strict replay A; replay B did not start and 79bb is not
qualified.**

## Outcome

The fresh r3 hardware gate passed completely on boot
`086de284-0771-4269-9cb2-e064fe303e40`: four-device identity, per-card
compute, peer read, four-rank XCCL barrier/all-reduce, coherent runtime, clean
journal, zero kernel taint, and clean postflight. Its sealed root is:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-79bb-20260824-086de284-venvlib-r3
```

The untreated zero-overlay candidate then ran from image
`sha256:786681b8aa4150d30e12af93b3038a03daba110719bf650a5c9d7c8804e0bdf3`
under the exact frozen runner, model, graph, cache, timing, and environment
contract. The campaign root is:

```text
/home/steve/qwen38-current-main-runs/tp1-untreated-79bb-20260824-r3
```

Two arms produced useful but incomplete evidence:

- the fresh diagnostic passed its exact canary, 25-row realistic benchmark,
  cache sealing, source checks, kernel guards, and cleanup. Its conventional
  99-interval median was `30.25266152916977 tok/s`, above the preregistered
  `30.2178` floor by `0.03486152916977` (`0.1154%`);
- strict replay A passed its exact canary, 25-row natural-EOS benchmark,
  immutable-cache check, and full quality battery. The quality result is an
  exact baseline match: 7/7 exact cases, 8/8 repeat-stability runs with one
  hash, the 8K needle at 7,617 actual prompt tokens, and all 24 baseline
  comparisons. Its observed median was `30.2372362888838 tok/s`, which is
  `0.07343875164618` (`0.2423%`) below the frozen
  `30.31067504052998` strict floor.

The strict measurement is not a completed speed-gate result. After the
workload and clean shutdown, the strict runner's mandatory remote freshness
check found that vLLM `main` had advanced from
`79bb395eea64dbfef99a55f010d2854db71f8571` to
`9f295fe8cee4cbd2b21a5ce3066cec026e4bd2af`. XPU-kernel main remained
`baaa05bb4e92901219a5a072dd63f2474896f6d1` and the official nightly remained
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
The runner therefore wrote `stale-before-promotion` and exited 5 before the
outer wrapper could write `current-base-strict-a-gate.status`. The wrapper
sealed `failed-incomplete mode=all rc=5`; replay B correctly remained absent.

This is intentional absolute-newest behavior, not a harness bug, correctness
failure, runtime failure, or completed speed-only regression. It does not
qualify 79bb, authorize TP2/TP4, or authorize deriving a compatibility packet.

## Evidence integrity

The r3 hardware manifest verifies 64/64 entries and hashes to
`41e76741dac933a8a6476d29316fd6e20210dde82805f48a433b36b7ed58135d`.
The campaign manifest verifies 158/158 entries and hashes to
`acdd66d9e566fe35469d0e19a223d6f8e8b4dd9ddde609679689dcfa0e6828ec`.
The frozen input manifest verifies 18/18 entries and hashes to
`0c68c34e6bbee6a544043d0567569da6cb5459d243fbe186cc47f3789714deea`.
The campaign manifest covers the non-cache raw evidence; the separately sealed
compiled-cache manifest verifies all 1,097 cache files.
The full machine-readable record is
[`2026-08-24-qwen38-79bb-r3-stale-during-replay-a.json`](../data/2026-08-24-qwen38-79bb-r3-stale-during-replay-a.json).

Both completed arms retained zero kernel taint, zero matching kernel rejection
events, no render holders, and no residual container. The strict cache manifest
was byte-identical before and after replay at
`55c88fc88bd92e9ab24a8979e852da04756ad0c107b67bc84c898644fde2fdfe`.

## Performance preservation and next action

R3 changes no protected floor, captured high, accepted decision overlay,
packet, or website cell. In particular, its diagnostic observation is
`0.00423847083023 tok/s` below the protected `30.2569` diagnostic high and
must not replace it; its incomplete strict observation cannot replace the
protected strict result.

Resolve all moving refs again, build the newest vLLM `main` (9f295fe8 at this
closure, or its successor) with the newest XPU-kernel `main` over the current
official nightly, and preserve accepted runtime/decision/source work as
separate versioned overlays. Qualify that exact base at TP1 first. Only a
complete current-identity TP1 result may advance to TP2 and TP4; broader matrix
and website coverage follows those current topology anchors.
