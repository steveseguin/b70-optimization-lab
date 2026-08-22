# Qwen3.8 MTP5/M6 Q64xK32 fresh two-GPU A-B-B-A r3 preregistration

Date: 2026-08-21

Status: **preregistered; single launch authorized after commit/push and hash
recheck; not yet run.**

## Basis and authorization

The original Q64xK32 operator campaign under the
[frozen preregistration](2026-08-21-qwen38-mtp5-m6-fa-q64k32-operator-prereg.md)
stopped infrastructure-invalid: all four GPU2 arms passed but GPU3's first
selector-off control froze at its first warmup synchronization — subsequently
classified as a valid GPU3 stock-control health failure. Today the authorized
host-wide `xe` recovery completed with its full gate green
([recovery note](2026-08-21-measuring-host-xe-recovery-2.md)), and the
fresh-root incumbent-control health retest passed
([r2 pass](2026-08-21-qwen38-gpu3-incumbent-control-health-r2-result.md)),
which authorizes exactly this: writing a new preregistration for a completely
fresh two-GPU eight-arm campaign.

## Contract

This r3 adopts the frozen operator preregistration's contract in full: same
bounded question, fixture/oracle identities, correctness and
failure-preservation contract, marker and mapped-library gates,
fresh-process A-B-B-A order (GPU 2 then GPU 3, stop on first arm failure),
40x100 captured-replay timing, and the conjunctive decision gates (paired
95% bounds per GPU; KV128 regression cap `+2.0 us/call`; KV1300 central
saving at least `21.844 us/call`). Frozen bytes rechecked this session:

- qualifier `31862ea6a8b9e11a59d643e0d3500179d938261e62b93fb920439c664ce21fbc`;
- driver `e7480d5768e366a5797f6c32afe8456281336238fb96e6cae4206b5257a53fb9`
  (mode 0755);
- control stage `/home/steve/staged-xpu-commitfix-graphfa-composite-20260820`;
- candidate stage root
  `/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r2` (immutable
  sealed r2 build; the build was never invalidated and is consumed by
  manifest identity through the driver's `check` gate — no rebuild).

**No evidence is carried over**: the r2 result root
`/home/steve/qwen38-mtp5-m6-fa-q64k32-abba-20260821-r2` remains terminal and
preserved, its GPU2 packets are context only, and all eight r3 packets are
fresh. The fresh immutable result root is

```text
/home/steve/qwen38-mtp5-m6-fa-q64k32-abba-20260821-r3
```

which must not exist before launch and is never reused after any stop.

## Launch condition and interpretation

Clean `main == origin/main` including this note; driver `check` against the
sealed candidate manifest must pass; no model workload, benchmark, or AOT
build may run on any card during the campaign (the TP1 lane server stays
down); quiet pre-launch kernel journal. One launch; on any arm failure the
campaign stops with its preserved failure receipt and no same-root retry.

A pass qualifies the Q64xK32 operator candidate on both GPUs and authorizes
only a separately preregistered endpoint/integration campaign toward the
MTP5 lane. It is not endpoint performance, target exactness, or promotion.
