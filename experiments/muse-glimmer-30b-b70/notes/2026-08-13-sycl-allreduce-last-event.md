# SYCL allreduce last-event readiness win

Date: 2026-08-13

## Why this was tested

The TP2/TP4 P2P recursive-doubling allreduce submitted one SYCL readiness
barrier per rank at every round-0 collective. Muse performs 104 target
allreduces per 52-layer verify pass, so TP4 paid 416 host submissions and 104
barrier commands per GPU. Creating those barriers lazily inside the copy loop
also made one bidirectional pull observe the other pull as preceding queue work.

## Patch and exactness

Source commit `a789ebe15` adds default-off
`GGML_SYCL_COMM_LAST_EVENT_READY=1`. After zeroing inactive slices and before
submitting any current-call P2P copy, it snapshots
`queue::ext_oneapi_get_last_event()` for every in-order queue. Round-0 pulls
depend on those producer events. Missing events, out-of-order queues, or query
exceptions use the unchanged barrier path.

The patch does not change tensor bytes, partners, scratch layout, copy sizes,
or arithmetic. Round 1 retains the prior remote `added[peer]` dependency, and
each F32 add remains `out += tmp` in the same recursive-doubling order. The
retained RMSNorm/scale/residual fusion is unchanged.

## Results

The 64-token screen was canonical and strongly positive. The authoritative
256-token last-event-off/on/off C/A/C was:

| arm | prose | code | JSON | mean tok/s |
| --- | ---: | ---: | ---: | ---: |
| barrier before | `55.636` | `80.405` | `98.088` | `78.043` |
| last event | **`57.697`** | **`83.153`** | **`101.352`** | **`80.734`** |
| barrier after | `55.654` | `80.433` | `97.979` | `78.022` |

The gain against pooled controls is **`+3.462%`**, with class gains of
`+3.688% / +3.400% / +3.385%`. All canonical hashes match. Accepted counts
are identical (`172 / 197 / 207`). Prose proposals were `1199 / 1199 / 1198`;
code and JSON proposal counts were identical. Request-time conversion using
`84 / 59 / 49` target rounds gives savings of approximately
`1.948 / 1.774 / 1.745 ms/round`.

Evidence:

- full identity:
  `sweeps/20260813-dflash-allreduce-last-event-full-cac.json`;
- smoke identity:
  `sweeps/20260813-dflash-allreduce-last-event-smoke-cac.json`;
- full JSONL SHA256:
  `f4fbe94799e3962c163a2ac29ee0ce7117b4ed46d3ecf4abce15152279bc1ddf`;
- smoke JSONL SHA256:
  `a2560021f43bf6b3b4176303fd43d4d09ae421ea5d5411802e7780819b29e708`;
- barrier-before/last-event/barrier-after log SHA256:
  `8b8a7defb81dc94f702531f9f4b200ee8632f3dfd33aa7a7e86efe295fffaf16`,
  `92ba426e977a13d449256c8142a2a578ea34e0db1b80df4dcd05ff2b875d45ca`,
  and `330336fc52beeb3fd989ffc16c7731aac80be04726a490c81507e1e2ff6905fd`;
- production restore:
  `data/muse-health-20260813-allreduce-last-event-restore.json` (models,
  cache-zero 512-token code, and vision all pass).

## Century arithmetic

Before this patch, the exact evidence-chain budget-15 DDTree projection after
the retained merge tree, 512-lane scan, and heap was `72.548 / 99.848 /
116.504 tok/s`, mean `96.300`, at zero tree-bookkeeping cost. Applying the
class-specific allreduce savings gives modeled round times `51.517 / 51.640 /
50.573 ms` and rates **`75.291 / 103.278 / 120.524 tok/s`**, mean
**`99.698 tok/s`**. A further uniform **`0.155 ms/round`**, plus the actual
cost of server tree bookkeeping, is still required. This is a major exact
kernel/runtime win, but not yet an honest measured >100 result.

## Fused remote-pull follow-up: rejected

A follow-up tried to halve steady allreduce commands by alternating
destinations: round 0 directly read local and remote tensors into scratch;
round 1 directly read local and remote scratch into the output tensor. The
expression grouping matched recursive doubling exactly, and explicit peer
events plus tail barriers closed producer and outbound-reader lifetimes.

The path is not viable on this runtime. The readiness-event control loaded and
completed its canonical 64-token suite at `69.032 / 113.995 / 219.903 tok/s`.
The fused candidate then stalled before health during initialization, after
target sampler construction and before draft-model load. A fresh, isolated
candidate-only launch reproduced the identical stall. Neither candidate
reached serving or produced a benchmark row. Both were terminated cleanly;
all four GPUs still enumerated, and production reloaded without a reboot.

Preserve but do not enable:

- failed source commit: `6117dae3a`;
- source revert: `25f179dc6`;
- interrupted C/A/C identity:
  `sweeps/20260813-dflash-allreduce-fused-pull-smoke-cac.json`;
- isolated proof identity:
  `sweeps/20260813-dflash-allreduce-fused-pull-proof64.json`;
- partial JSONL SHA256 (control row only):
  `1e82f65e0dc3d7d48c3b8bf04c5f18b5d0e5d6c2eb1572bb98ed6ee31b2751d9`;
- C/A/C candidate-stall log SHA256:
  `e94c4fc5ddba9a306a949fb8c6170187b5b8603bd2d606d880cd5f8a7c08370c`;
- isolated candidate-stall log SHA256:
  `fdc3f64d7a845183b717d24fb81fad456eb452bae32afb650ab289406e009b57`;
- production restore:
  `data/muse-health-20260813-fused-pull-revert-restore.json`.

This closes fine-grained remote kernel loads as the next allreduce command
reduction. Retain the event-readiness win; pursue the narrowly scoped final
allreduce-add plus RMSNorm/scale/residual fusion or another independent exact
kernel saving instead.
