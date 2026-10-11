# Packet 16 two-card resident decode: GPU page fault on first compute (2026-10-11 09:09:45 UTC)

**This is the second GPU fault on this boot** (boot 2026-10-11 01:40:53 UTC; first fault
02:34 UTC on `0000:43:00.0`). Under the standing rule device launches are halted and the
owner decides on a reboot. No reboot, driver reset or hard kill was done.

## What ran

A coordinator speed diagnostic, not the prepared W2 window: packet 16's W2 command line
on cards 2+3 (`--cards 2 --memory resident --stage decode --max-new 64 --gemv frozen
--nongemv parallel --context 256`) **without `--oracle`**, because the native program
stops at the first layer that differs from the v1 CPU oracle and v1 cannot match device
arithmetic. W1 on card 3 had passed minutes earlier (48/48 layer hashes and the token
equal to packet 13's device result, 485 s). Two things differed from the prepared W2:
no `--oracle`, and the environment carried `NEOReadDebugKeys=1 EnableDeferBacking=0`
(the lab's multi-card host-memory setting). [Launch script](coordinator-launch.sh).

## What happened

- 09:08:52 start. Both owners loaded every resident weight: 26,480,547,388 and
  26,779,689,364 owned bytes (first measured fit of the two-card resident plan; host
  MemAvailable stayed near 67–70 GB, GPUActive 15 MB).
- 09:09:45, right after the last upload and before any site was recorded
  (`sites.jsonl` empty, `prefill-timings.jsonl` empty): on **both** `0000:47:00.0` and
  `0000:43:00.0` a GPU page fault (`Fault response: Unsuccessful -ENOENT`, faulted
  address `0x0000caac549d0000`, ASID 599 on 47:00.0), `Engine memory CAT error [18]`,
  engine reset of the compute engine, timed-out job in `own-rt-iq3 [183867]`, device
  coredumps. No GT reset line, no lockup, host responsive.
- 09:09:52 the coordinator's watcher sent one cooperative SIGINT. The program printed
  `cooperative stop` and is parked with its owners (PID 183867, one spinning thread,
  about 53 GB of VRAM held on those two cards). It was left alone: a hard kill is a
  teardown transition and is treated as a fault.

A page fault on an unmapped GPU address at the first submission after loading, on both
cards at once, is the signature of a kernel touching memory that is not mapped in its
own card's address space. It is treated as a software defect of the never-before-run
two-card resident path until shown otherwise; the changed NEO setting is the second
suspect. Card `0000:43:00.0` is the card with the hardware-fault history, but a
hardware fault does not produce a simultaneous page fault on a second card.

## Evidence here

`kernel-window.txt`, `devcoredump-card0.txt` (43:00.0), `devcoredump-card2.txt`
(47:00.0), `stdout.txt`, `coordinator.log`, `progress-tail.jsonl`, `plan.json`,
memory traces. The full run directory stays in the ignored build tree
(`build/w2x-cards23-speed-a`).

## Card index note

The runtime's "cards 2+3" are PCI `0000:47:00.0` and `0000:43:00.0`. The one-card
windows on "card 3" therefore ran on one of these two.

## Correction and audit result (09:57 UTC)

The CPU audit in [packet 19](../../../packet19-depcheck/ROOT-CAUSE.md) corrects two
statements above. This command does not write per-site progress, so the empty
`sites.jsonl` shows only that no token completed, not that the fault came at the very
first kernel. And the two cards faulted on two different addresses
(`0x0000d556a9ed0000` on 43:00.0, `0x0000caac549d0000` on 47:00.0), 0.3 ms apart.

The audit found no missing dependency, wrong-card binding or premature release in the
application code (it built a sanitizer that runs the plan in randomized
dependency-consistent order to check this). It ranks first something the CPU cannot
show: packet 16 passes events of one card's queue as dependencies to the other card's
queue and copies between cards without draining both on the host, which packet 14's
passing two-card run never did. The NEO key added for this run cannot be judged from
code and stays a suspect. Nothing here is proven until a device run.

Consequence: packet 18 gets host fences at every card crossing (packet 14's proven
pattern), index guards, and a required few-KiB two-card canary window before any
weights are loaded; its windows refuse to start with NEO debug keys in the environment.
