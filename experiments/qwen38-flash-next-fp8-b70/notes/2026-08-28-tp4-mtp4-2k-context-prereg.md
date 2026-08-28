# Flash-Next TP4 native-MTP4 exact-2K context preregistration

Date: 2026-08-28

## Purpose and evidence boundary

Classify the missing TP4/EP4/eager/text/native-MTP4 active-2K matrix cell with
one fresh server boot and at most two identical requests. MTP4 already passes
its configured-512 screen, while active-1K and exact-4K are retained as
separate quarantines. The exact-2K MTP0 output authority is sealed. This arm is
additive: it cannot lower, replace, or relabel any captured speed, quality pass,
preferred recipe, or existing matrix cell.

## Frozen server identity

- model `Qwen/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, from the validated local-NVMe
  path `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- kernel checkout `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- loaded stage
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`, built from
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager, graph off, text only, native MTP4, one sequence, 64 maximum
  batched tokens, prefix caching and async scheduling off;
- BLHNC automatic-precision KV, exactly `341266432` bytes / 29 blocks, the
  exact MTP4 allocation used at configured 1,536 and 4,352. Do not predict a
  token capacity from those arms; require the fresh boot to report at least
  3,072 tokens;
- selective UVA placement of the PLE n-gram and input embeddings, 12.22 GiB
  reported per rank;
- configured maximum 3,072, port 19665, attempt 1, no diagnostics or reasoning
  parser.

Launcher:
`tools/launch-tp4-ep4-eager-mtp4-3072-headroom29.sh`.

## Frozen artifacts

- tools commit `beda233c3`;
- shared base launcher SHA-256
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- MTP4 exact-2K wrapper SHA-256
  `7ff6398a7f880c85d57f4fec3d40ca789bdde6201f887d33615b878e500923d3`;
- detached supervisor SHA-256
  `69e341ded934508d9cc0ab303cdfad95e8673e05f6932d166616af76dff38d21`;
- request client SHA-256
  `1c76a500c12a1f3ddaa899e1f26342d764d3076aa9b1802c43e92d5175a3de06`;
- descendant-aware lifecycle test SHA-256
  `afe7c54491e16e513614fe7c793e14247f3edd5fb6b1958ff61057c492a663b1`;
- exact-depth harness SHA-256
  `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`;
- exact-depth fixture SHA-256
  `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`;
- MTP0 exact-2K repeat-v2 receipt SHA-256
  `ecfbd7bf09fc2637bbee9be4658e1febc8ec8cc19f6f61c71864a615a2b25794`;
- raw MTP0 exact-2K receipt SHA-256
  `3875376d98843afa201390b7837686dd9be8c2d645df968a474c704bae236e81`;
- frozen MTP0 output-token-ID SHA-256
  `5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e`.

The MTP0 authority used vLLM `658965050` and a `201326592`-byte cache. It is a
frozen cross-lane parity oracle, not an isolated causal test of MTP4. A mismatch
is a scoped deterministic parity quarantine and must not be described as proof
that MTP4 alone caused the divergence.

## Lifecycle gate

The corrected supervisor resolves the unique launcher below GNU `timeout` and
signals that launcher, allowing the base launcher's EXIT trap to stop the
separate server session. The synthetic test at commit `5989e7419` exercised the
same timeout-to-launcher-to-detached-listener shape and passed only after the
server process, listener, compile path, and RPC path were absent. Never reuse
the executed active-1K supervisor version that signalled GNU `timeout` and left
the detached server alive.

Launch supervisor and clients detached from interactive tooling. Interactive
work may poll only durable PID/rc/log/result files. The supervisor owns the
2,100-second / 35-GPU-wall-minute cap. Its only valid stop sentinel is exactly:

```text
STOP after completed preregistered requests
```

Before `/tmp` evidence can be lost, copy and hash the stop sentinel,
supervisor/child/launcher PID files, supervisor rc/output, both client
PID/rc/log files, final journal, and final passive process/listener/path/card
census into the run directory.

## Ordered execution

1. Require a clean main worktree containing this preregistration, the exact
   model/source/runtime hashes, four expected idle B70s, a fresh four-rank
   collective, staged imports and schemas, four 12.22-GiB placement receipts,
   exactly 29 cache blocks, freshly reported capacity of at least 3,072 tokens,
   correct served identity, and a healthy API.
2. Snapshot endpoint counters, then run the sealed exact-depth fixture once at
   depth 2,048 through the `vllm` adapter with temperature zero, top-p one,
   seed one, ignored EOS, no prompt truncation, no special tokens, cache
   disabled, and 128 requested output tokens. Add no warmup. The engine's
   worker-response gate remains 300 seconds; the established HTTP client and
   outer bounds remain 360 and 370 seconds.
3. Require the generic receipt gate, exactly 2,048 prompt and 128 output tokens,
   a length stop, zero cached tokens, 128 returned token IDs, the frozen MTP0
   token-array hash, a complete 100-event / 99-interval decode window, positive
   MTP4 draft/draft-token/accepted-token counter deltas, and positive accepted
   deltas at all four positions zero through three.
4. Only after all request-one gates pass, create this exact one-line sentinel:

   ```text
   PASS request1 exact usage length MTP0 token hash cache-zero 100-events 99-intervals and MTP4 positions 0 1 2 3
   ```

   Then repeat the identical request once. Require the same gates, the same
   MTP0 hash, and exact token-array equality with request one. The repeat is a
   determinism sentinel, not another independent speed sample.
5. Capture final endpoint counters and the bounded shutdown evidence. Write the
   exact supervisor stop sentinel only after all authorized request and final
   counter evidence is durable. Require supervisor rc zero, no listener,
   server process, compile path, or RPC path, and four discoverable idle cards.

## Stop rules and frozen interpretation

Stop immediately on any repository/source identity, placement, cache block,
capacity, health, token count, length stop, output hash, cache-zero, timing
window, MTP counter/position, API, host-health, or teardown mismatch. If request
one fails, do not create its gate sentinel and do not send request two. Do not
raise the 300-second engine response gate, 360-second client bound, 370-second
outer client bound, 2,100-second supervisor cap, cache allocation, or add a
warmup. Do not retry under this preregistration.

Any B70/reset/fatal, uncorrected link/storage, or I/O event is Grade D. Count
and disclose corrected-only local-NVMe records. Consistent with the active-1K
policy, corrected-only records block clean-host and deployment qualification;
they do not erase an otherwise exact Grade-C matrix screen.

A complete pass adds only the TP4/eager/native-MTP4/active-2K cell as Grade-C
research evidence. Any stop is retained as a bounded quarantine with its
observed diagnostic evidence. Neither outcome changes MTP4/512, active-1K,
exact-4K, any featured result, or any prior captured speed.

## Result

The single authorized boot passed every frozen startup gate: exact source and
runtime identity, fresh four-rank collective, four 12.22-GiB placement
receipts, exactly 29 cache blocks, 3,563 reported cache tokens, correct served
identity, and health. Each rank reported 32.06 GiB of model allocation.

Request one began at 01:19:39 with the exact p2048/o128 fixture. The client
reached its unchanged 360-second bound and exited `2` without writing a
receipt. No HTTP status, response body, usage, output token, parity hash,
timing window, or speed is available. About five seconds later the engine
independently reported its own sampling RPC timeout. Its fatal scheduler
snapshot showed 384 computed prompt tokens, 64 scheduled tokens, zero output,
and no speculative statistics. This proves partial prompt work and zero output
at the engine snapshot; it is not a completed response and establishes no
causal direction between the two timeouts. Request two was not sent.

The exact stop sentinel was then used. The corrected descendant-aware
supervisor returned zero and final passive checks found all recorded
supervisor, launcher, server, and client PIDs absent, no port-19665 listener,
and no compile or RPC path. The API logged application shutdown complete.
Nevertheless, the teardown window recorded one compute- and one copy-class
reset on each of all four B70s plus 60 unsuccessful fault responses. All four
cards were subsequently rediscovered at low memory use, but no post-reset
collective or known-good generation canary was run. Seven APEI records, one
with two sections, separately retained eight corrected receiver events for the
local NVMe; none was fatal or uncorrected.

The active-2K MTP4 cell is therefore a Grade-D bounded quarantine with no
speed, quality, parity, MTP-acceptance, or deployment credit. It must not be
retried under this preregistration. MTP4/512, active-1K, exact-4K, every
featured result, and every captured speed remain unchanged. Compact receipt:
[`20260828-tp4-mtp4-3072-context-attempt1-bounded-negative.json`](../data/20260828-tp4-mtp4-3072-context-attempt1-bounded-negative.json).
