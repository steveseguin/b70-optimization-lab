# Flash-Next TP4 native-MTP4 active-1K preregistration

Date: 2026-08-28

## Purpose

Classify the missing TP4/EP4/eager/text/native-MTP4 active-1K practical-matrix
cell with one fresh boot and at most two identical requests. MTP4 passes its
configured-512 screen and is quarantined at exact 4K. This additive arm cannot
lower or replace either result or any other captured speed.

The immediately preceding MTP3/1K arm was externally signalled when its
interactive process session ended during request one. This arm therefore runs
the frozen launcher and clients detached from the interactive session, with
PID, log, and exit-code sentinels. Detachment changes orchestration only; it
does not change model, runtime, cache, request, or evidence gates.

## Frozen identity and artifacts

- verified local model revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` at
  `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, kernels checkout
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, staged build
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager/graph-off, text only, native MTP4, automatic BLHNC KV,
  prefix cache and async scheduling off, no reasoning parser or diagnostics;
- maximum length 1,536, one sequence, 64 maximum batched tokens;
- exactly `341266432` cache bytes / 29 blocks, with at least 1,536 reported
  tokens required;
- selective UVA placement with four exact 12.22-GiB receipts;
- campaign `qwen38-flash-next-fp8-tp4-ep4-eager-mtp4-1536-r1`, attempt 1,
  port 19664;
- base launcher SHA-256
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- wrapper `tools/launch-tp4-ep4-eager-mtp4-1536-headroom29.sh` SHA-256
  `907eadac18cf17de65fd6cb09b93341a0e2d756b016cbbe80aafd418577dfd8c`;
- detached supervisor `tools/supervise-tp4-mtp4-1536.sh` SHA-256
  `67e4962a8c4b6d87097d67cd301d8c8adb0d612080201dc8df3e363eec5a8d78`;
- fail-closed client `tools/run-tp4-mtp4-1536-client.sh` SHA-256
  `d9fec4584841ace0f6ae0d9fef6c16db0abc246ddf39505be508705c44c471b8`;
- deterministic harness SHA-256
  `d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4`;
- raw MTP0 `context-r1` authority SHA-256
  `ad8de7521078654fe12f0f0c247b6c4f34897faa188e3ccd993e9dc04a07c874`;
- frozen completion-text SHA-256
  `5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0`.

The MTP0 authority used vLLM `658965050` and a smaller cache allocation. A
hash mismatch is therefore a scoped cross-lane parity quarantine, not isolated
proof that MTP4 caused a semantic difference.

## Detached execution contract

After clean idle-card and listener checks, record a journal cutoff and launch
the committed supervisor with `nohup setsid`, stdin from `/dev/null`, output in
`/tmp/q38-mtp4-1536-supervisor.out`. The supervisor PID, bounded-launcher PID,
and atomic exit sentinel are exactly `/tmp/q38-mtp4-1536-supervisor.pid`,
`.child.pid`, and `.rc`. The supervisor applies `timeout --signal=TERM
--kill-after=30s 1800s` to the launcher; rc 124 is an explicit watchdog stop,
not unexplained process death. Poll only those sentinels, the committed run
directory, failure markers, and health endpoint. Do not signal it through the
interactive tool session.

After the final authorized request and evidence snapshots, create exactly
`/tmp/q38-mtp4-1536-supervisor.stop` with the one line `STOP after completed
preregistered requests`. The supervisor observes that sentinel and signals its
bounded child, allowing the base launcher's cleanup trap to stop the server.
An invalid stop sentinel is a teardown mismatch.

Each client is likewise launched with `nohup setsid` through the committed
fail-closed client wrapper. It refuses overwrite, requires pre-request metrics,
writes exact `client-requestN.pid`, `.log`, and atomically published `.rc`
sentinels in the run directory, and moves any unexpected partial JSON aside on
failure. Its own 370-second watchdog bounds the 360-second harness client.
Request two additionally requires the exact one-line
`request1-gates-passed.txt` sentinel, so it cannot run before external
adjudication of request one. Request flags are:

```text
--base-url http://127.0.0.1:19664
--tokenizer /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
--prompt-tokens 1038 --shared-prefix-tokens 0 --prompt-salt context-r1
--output-tokens 256 --concurrency 1 --warmups 0
--timeout 360 --seed 20260606
```

Request one writes only `bench-context1k-o256-c1-r1.json`; the repeat writes
only `bench-context1k-o256-c1-r2.json`. Missing exit/PID sentinels or unexpected
process death is a stop.

## Ordered gates

1. Require exact hashes, clean sources, four idle/discoverable B70s, fresh
   four-rank collective, staged schemas/imports, four placement receipts,
   29-block capacity, served identity, and healthy API.
2. Snapshot metrics and run request one. Require exactly 1,024 prompt and 256
   output tokens, a complete stream, frozen MTP0 text hash, present cache metric
   with zero delta, positive MTP4 drafts/draft tokens, and positive accepted
   deltas at positions zero through three.
3. Only after every request-one gate passes, send the identical repeat. Require
   exact text equality, the same usage/hash/cache-zero gates, and positive
   isolated MTP4 counters at all four positions. It is a determinism sentinel,
   not a second performance sample.
4. Capture hashes, metrics, journal through shutdown, listener/process census,
   and four-card discovery. One boot, two requests, 30 GPU wall minutes.

## Host policy and interpretation

Any B70-named event, uncorrected/fatal PCIe condition, reset, disconnect, I/O
or filesystem error, changed/unreadable artifact, collective/request failure,
unexpected process death, or teardown mismatch is a Grade-D quarantine.
Corrected-only NVMe receiver reports with zero uncorrected status are counted
and disclosed; prospectively they block clean-host/deployment qualification but
do not erase otherwise exact Grade-C matrix evidence.

Stop after any request-one mismatch; do not send request two, change bounds,
add warmup, change storage/cache, or start a second boot. A pass adds only the
MTP4 active-1K Grade-C cell. A stop is retained as quarantine. MTP4/512,
MTP4/exact-4K, all other depths, and all prior captured speeds remain unchanged.
