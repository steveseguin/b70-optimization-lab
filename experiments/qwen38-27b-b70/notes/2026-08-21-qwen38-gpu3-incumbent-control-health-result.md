# Qwen3.8 GPU3 incumbent-control health diagnostic result

Date: 2026-08-21

Classification: **valid GPU3 stock-control health failure; timeout-terminated**

Preregistration:
[`2026-08-21-qwen38-gpu3-incumbent-control-health-prereg.md`](2026-08-21-qwen38-gpu3-incumbent-control-health-prereg.md)

Structured summary:
[`2026-08-21-qwen38-gpu3-incumbent-control-health-result.json`](../data/2026-08-21-qwen38-gpu3-incumbent-control-health-result.json)

## Outcome

The fresh-root physical-GPU3 stock-control diagnostic failed its exact health
boundary. The worker passed repository, stage, device, and mapped-library
identity gates; returned from exactly ten asynchronous FlashAttention Python
calls; and published `sync-enter`. It never published `sync-return`. At
`60.05274560902035` seconds from the supervisor's pre-spawn deadline origin,
the watchdog durably recorded the timeout, sent `SIGTERM`, observed child
return code `-15`, and verified that the process group was empty. The frozen
validator returns `14` and classifies the terminal packet as
`gpu3-incumbent-control-timeout-terminated`.

Passive kernel-journal evidence records a Xe/GuC timeout-and-reset storm that
overlapped the diagnostic and began before the observed FA prefix. One exact
timed-out-job line names `python [938011]`, the same PID/PGID/SID sealed for the
worker. This corroborates that the failed health boundary coincided with a
kernel-visible timeout for that process; it does not show that this worker or
the stock FA prefix caused the wider storm. Nor does it localize the fault to
hardware, driver, firmware, runtime, or a particular one of the ten submitted
FA calls.

## Sealed evidence

The preserved root is
`/home/steve/qwen38-gpu3-incumbent-control-health-20260821-r1`:

- `contract.json`: SHA-256
  `7cd5bfda4e6bf90c59f8ff29cc967d39903bef8ddc256abc571a338a8b635861`;
- `terminal.json`: SHA-256
  `e91f7791278d3fb06f2e3683d3d779ea928fe1b40cebb3e35358bed29c25c76d`;
- `cleanup-state.json`: SHA-256
  `fa9bb851efb4ea04d6e38c5403ae0a5d67879f5b86193069ea617e6e06d57d52`;
- `worker-phases/0014-sync-enter.json`: SHA-256
  `8a58f1bfb8a126d4fb3be4ed38f2a485ae67026e2001604ca4de11d5aab81e72`;
- `supervisor-phases/0002-timeout-before-term.json`: SHA-256
  `56d8a77fad13bcbbc4c2f35aa85182cd1e2040a54b6eb6231e6a4bbf3549913e`;
- immutable worker stdout and stderr: both empty at SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The chain contains exactly `worker-start`, `base-and-stage-verified`,
`device-bound`, `stock-maps-bound`, ten ordered `fa-launch-returned` receipts,
and `sync-enter`. It contains no `sync-return`, `worker-complete`, worker result,
or worker failure packet. The ten return receipts span only
`0.154995616` seconds. That interval is Python submission evidence, not device
timing or proof that any submitted call completed on the GPU.

The worker was exact PID/PGID/SID `938011`, boot ID
`256bc838-c015-4c91-a8f9-363d281f7555`, start ticks `32442800`. Cleanup sent
`SIGTERM` but not `SIGKILL`, recorded no errors or late signals, and ended with
a verified empty group and `unkillable=false`. No process was left behind.

The identity was physical GPU `3`, `ZE_AFFINITY_MASK=3`, logical `xpu:0`, Intel
Arc Pro B70 UUID `868023e2-0000-0000-4700-000000000000`, PCI context
`0000:47:00.0`, and stock stage
`/home/steve/staged-xpu-commitfix-graphfa-composite-20260820`. The complete
20-file graph manifest was rederived at SHA-256
`47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da`.
The exact extension, device, and stock libraries were mapped; the maps view has
SHA-256 `8ffa0c9de696a852e04759d40fd8bd75196cdbe653f29afa216510230a6f7944`.
Both experimental policy selectors were `0`. No candidate was loaded.

The operator shape was the preregistered FP16 stock KV-128 path: rows `6`, TP2
local Q heads `12`, local KV heads `2`, head dimension `256`, block size `64`,
paged causal KV, `is_mix_batch=True`, and forced chunk decode. There was no
model load, XPU graph capture, correctness oracle, mutation screen, or timing
sample.

## Passive kernel evidence outside the sealed root

An exact-window read of the existing kernel journal used host timezone
`America/Toronto` (`-04:00`) and `short-iso-precise` output:

```bash
sudo -S -p '' journalctl -k \
  --since '2026-08-21 02:46:25' \
  --until '2026-08-21 02:47:45' \
  --no-pager -o short-iso-precise < /home/steve/SUDOPASSWORD.txt |
  rg 'xe 0000:47:00.0|Engine reset' |
  sha256sum
```

The password file supplied only `sudo` stdin; no credential bytes were printed
or preserved. The filtered stream produced SHA-256
`43b6cd71dedbe2d4bf237e0d95ab827b027eb62b5cd53247fd890993cf71e249`.
It is passive host evidence, not an immutable file in the sealed diagnostic
root. The normalized counts were `1863` `Kernel-submitted job timed out`
records, `1863` flags-`0x73` `Timedout job` records without a process name,
`1242` each of trying-reset/reset-queued/reset-started/reset-done, one Xe
coredump, one coredump-path prompt, one exact worker-PID timeout, and one engine
reset.

The decisive chronology is:

- `02:46:38.028384`: the Xe coredump was created, before the observed worker FA
  prefix;
- `02:46:57.660090`: `Timedout job: seqno=4294967169, lrc_seqno=4294967169,
  guc_id=6, flags=0x20 in python [938011]`;
- `02:46:57.815687177` through `02:46:57.970683474`: the ten sealed FA-return
  receipts;
- `02:46:57.986973770`: sealed `sync-enter`;
- `02:47:31.754952`: `Engine reset: engine_class=ccs, logical_mask: 0x1, guc_id=2,
  state=0x289`.

The timeout naming the child precedes the first FA-return receipt, and the
larger storm predates the prefix. The PID match ties one passive kernel timeout
to the sealed worker process, not to a specific FA call. The journal does not
prove a persistent device fault or distinguish a device fault from
driver/firmware/runtime interaction. No new GPU query, recovery, or device
operation was performed for this result packet.

## Decision

Preserve r1 and do not retry it in place. This failure does not qualify or
reject Q64xK32, carry the prior GPU2 packets into a future comparison, authorize
a candidate arm, or authorize a model/full-25 run. It supplies no model
correctness, quality, throughput, or timing inference.

The only defensible next boundary is a separately authorized, host-wide
all-four-B70 `xe` recovery under the policy in
[`docs/local-ops.md`](../../../docs/local-ops.md), beginning with its passive
ownership, display, and kernel-command-line checks. That policy forbids PCI
FLR and requires the complete post-reload health gate. After recovery, any
further stock-control health test must use a new root and a new
preregistration. A candidate or full two-GPU operator campaign remains
unauthorized until a fresh incumbent control passes; no recovery or follow-up
launch was performed here.
