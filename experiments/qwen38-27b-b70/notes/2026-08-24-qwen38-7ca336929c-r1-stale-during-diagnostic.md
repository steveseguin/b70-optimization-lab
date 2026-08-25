# 7ca r1 closed stale during control fresh diagnostic

Date: 2026-08-24. Status: **failed-incomplete; stale before promotion.**

The audited 7ca untreated TP1 r1 packet passed its fresh hardware gate, loaded
the exact zero-overlay candidate, directly and ordinarily verified all 19 model
files, returned exact canary content `14` with zero cached prompt tokens, and
completed the workload for all 25 diagnostic benchmark rows. Its mandatory
post-workload freshness check then found that vLLM `main` had advanced from
`7ca336929c169fee1210dd5293029d78811fba27` to
`e3dde1ee9bfab341592fbfae1f170795568b83ac`. XPU-kernel main remained
`baaa05bb4e92901219a5a072dd63f2474896f6d1`, and the official nightly
remained
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
The runner intentionally wrote `stale-before-promotion` and exited 5.

This is append-only stale evidence, not a completed TP1 qualification, strict
or quality result, current record, or speed regression. It authorizes no TP1
decision packet, TP2/TP4 run, cache promotion, website measured cell, or change
to any protected speed.

## What the workload completed

The conventional 99-interval diagnostic median was
`30.272705632473954 tok/s`, `0.05490563247395386 tok/s` (about `0.1817%`)
above the frozen `30.2178 tok/s` diagnostic floor and
`0.015805632473952613 tok/s` above the protected `30.2569 tok/s` diagnostic
high. The full diagnostic statistics were:

- p10 / mean: `30.175887561862872 / 30.301752402752257 tok/s`;
- minimum / maximum: `29.646438843223095 / 30.896014068130558 tok/s`;
- standard deviation: `0.22081091283793464 tok/s`;
- legacy inclusive median: `30.57849053785248 tok/s`.

All 25 rows were eligible, prompt-cache counts were zero, and the benchmark's
fixed-suite freshness checks passed. This arm deliberately used
`ignore_eos=true`; it did not request the strict quality battery. Upstream moved
before the wrapper could write the diagnostic speed-gate artifact, so the
diagnostic arm itself did not pass and the observation cannot replace the
protected high despite exceeding it.

The candidate container was removed before the freshness check. Cleanup sealed
kernel taint 0, zero matching kernel rejects, zero accepted corrected-NVMe
events, and no render holder. The fresh compile produced 1,097 regular cache
files with manifest SHA-256
`c2c1fee2b36cde801e6d289aec559ae593af03b7beeef5020ab658b35c3b8ad6`.
A read-only closeout census found 212 directories at directory-set SHA-256
`607db9ede047f233d097f97618bf3ccb99340aaa845a249c68c39cbce152c072`
and confirmed `vllm/dummy_cache` absent. Because exit 5 propagated immediately, the
successor-only dummy-cache normalization and canonical file/directory manifest
freeze were not reached. Strict replay A and replay B never started, and no
aggregate qualification result exists. Do not normalize or reuse this cache on
a successor build.

## Evidence and preservation

The hardware root is:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-7ca336929c-20260824-086de284-venvlib-r1
```

Its 70/70 manifest hashes to
`939bf2b26c38a293a69fc5442c4ba6a1ac835a0e29f9d2b6b8060845bc7b506c`.
It passed four-device identity and compute, peer read, four-rank XCCL
all-reduce, coherent PyTorch runtime, root-NVMe health, repository postflight,
and clean process/container/device postflight.

The campaign root is:

```text
/home/steve/qwen38-current-main-runs/tp1-untreated-7ca336929c-20260824-r1
```

Its 349/349 evidence manifest hashes to
`e39c9782d2decb531ff253e76a02a50053164f6e11ed92417087fa6d44124411`;
the frozen 267/267 input manifest is
`ca07959402fa4486c295b1ee3fb3a332567f1d05dbab23f833f4770e4e1091bf`.
The exact both-current image is
`sha256:b7bc798035552130e96f3649c21541f1b40fa3c5db0558631e44e461297196a4`,
and its build receipt is
`e090d5a7694ffa6f595d84e6adc38a3da6cd33020e5c7f4d96ae678ecd146622`.
Launch and close-time lab identity both remained
`8621f019003d5fe6ccd5f055f97fa07c67364d5d`.

The complete protected-performance subobject remains
`e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f`,
and the whole protected manifest remains
`4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454`.
The disabled, unapplied TP2 78-decision and TP4 152-decision bundles verify
exactly at
`65c574c24d24804d250e5179e9a202ec9e77e8c5740cea121b7660d8ee854757`
and
`a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2`.
No overlay was applied and no protected floor or high changed.

The machine-readable closeout is
[`2026-08-24-qwen38-7ca336929c-r1-stale-during-diagnostic.json`](../data/2026-08-24-qwen38-7ca336929c-r1-stale-during-diagnostic.json).
Keep both roots and their frozen packet immutable.

## Next gate

Resolve vLLM main, XPU-kernel main, and the official nightly again. Build
`e3dde1ee9b` only if it is still the literal newest vLLM head; otherwise build
its newest successor. Preserve the accepted overlays without applying them to
the new zero-overlay anchor. Qualification order remains untreated TP1, any
required fresh TP1 decision packet, TP2 zero-overlay plus a fresh 78-decision
remap, then TP4 zero-overlay plus a fresh 152-decision remap. Broader website
matrix work follows qualified current topology anchors; no historical value is
lowered to make a newer base pass.
