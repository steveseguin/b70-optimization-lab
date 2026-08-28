# Qwen3.8 Flash-Next TP4 MTP0 current PIECEWISE graph anchor preregistration

Date: 2026-08-28

## Purpose and authority

Run one bounded current-runtime TP4/EP4 text-only MTP0 PIECEWISE classification
after the eager attempt-4 anchor. The only serving treatment is graph mode. The
cell keeps the eager anchor's model, source, staged kernels, placement, cache,
context ceiling, scheduler, and benchmark identity.

This is deliberately experimental. Current vLLM warns that XPU graph support is
experimental and currently supports only single-GPU execution. A TP4 boot,
capture, or quality failure is therefore a useful bounded negative, not a
performance regression. A passing run is a same-boot Grade-C lab screen for the
short TP4 PIECEWISE MTP0 cell only. It cannot replace, lower, or relabel eager
attempt 4, any legacy graph result, an MTP result, or another retained speed.
No LocalMaxxing submission or production claim is authorized.

## Frozen identity

- model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`
- model: `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`
- vLLM: `1372c62d975c554f4b465c8299bc5f3295301ceb`, clean
- XPU kernels: `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`
- staged runtime build: `2f829747503c77d4814834dffd0840fb1dd9f75a`
- TP/EP: `4/4`; MTP0; direct answers; no reasoning parser
- max model length `4352`; max sequences `1`; max batched tokens `64`
- cache `201326592` bytes, BLHNC, prefix cache off; require at least 4,224
  exposed tokens
- unchanged selective UVA placement: 12.25 GiB/rank for the PLE and input
  embeddings
- async scheduling off; fresh attempt `1`; port `19674`
- fresh run/cache/compile/RPC paths use campaign
  `qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1`

The graph treatment is exactly:

```text
VLLM_XPU_ENABLE_XPU_GRAPH=1
--compilation-config {"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}
--cudagraph-metrics
```

`--enforce-eager` is absent. The packet rejects the legacy `XPU_GRAPH`,
`VLLM_XPU_GRAPH`, `VLLM_XPU_FORCE_GRAPH_WITH_COMM`, and
`VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE` controls rather than silently carrying
unknown current-source settings. Effective engine configuration, the explicit
mixed prefill/decode PIECEWISE capture marker, and a runtime metric-table row
with `CUDAGraphMode.PIECEWISE` are all mandatory. Requested configuration alone
does not earn graph credit.

The eager base remains unchanged at SHA-256
`62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`.
The isolated packet files are:

- graph base launcher
  `launch-tp4-ep4-piecewise-mtp0-4352.sh`:
  `533be64e1c7584448c07a5f8895301a32288f4b0472948a91d87235e78c6f09f`;
- fixed wrapper `launch-tp4-mtp0-current-piecewise-graph-a1.sh`:
  `52642fdff6a4cd208241aaee0ad3bc3c049c1b46915457dec985ab23ebeb3ec5`;
- client `run-tp4-mtp0-current-piecewise-graph-a1-client.sh`:
  `5886f5ba6127826f1122bc8ac26d4c1b328d9ab34674051e50cb5d985dbdaaaf`;
- supervisor `supervise-tp4-mtp0-current-piecewise-graph-a1.sh`:
  `414dd8ad9a1d07ae78b66512bdfdb1d453516a35c6528ecf0e6cc2b94bf7c3df`.

The client also pins the eager-a4 quality oracle at
`c0c76ab19bb93963fd2817930b0ce4a3edfd73861bdab75377ad03f6a5be5c83`,
the direct-quality helper at
`8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de`,
and the established short benchmark at
`d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4`.

## Ordered gates

1. Fresh-path, exact model/source/stage, four-card idle, four-rank collective,
   configuration, cache, and owned-server gates.
2. Effective PIECEWISE configuration and positive capture evidence. A fallback
   to NONE, absent runtime evidence, or inherited legacy graph control stops.
3. Exact cache-zero `OK` recovery canary: 17/2/19 usage, normal stop, frozen
   hash.
4. The seven direct semantic cases against the eager-a4 oracle, plus one color
   repeat. Accept the frozen 6/7 state only when the sole miss remains
   `code_execution=30`; require exact comparator parity and cache zero.
5. Before any speed work, alternate two deterministic families for 96 calls
   each on the same server:
   - color: exact `blue, green, red, yellow`, hash
     `3b0b3192cd70de9c19caf7a6f6f69a4dda63cc4e66049c2cf9c15633103896b7`,
     exact 37/8/45 usage;
   - JSON: exact `{"answer": 42, "unit": "widgets"}`, hash
     `250a25b051da4e7e82761d80134aea4bd17bac1d4644cda1c5df3be93d4e3a91`,
     exact 36/14/50 usage.
   Every response must stop normally with both prompt-cache counters zero.
6. Only after 96/96 plus 96/96 and runtime PIECEWISE evidence pass, run the
   established p146/o256/c1 short protocol: one conditioning request before
   row 1, then two zero-warmup rows. Require exact 146/256/402 usage and output
   hash `5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0`.
7. Controlled stop and descendant-aware cleanup, followed by clean port and
   scratch state, exact four-card discovery, under-256-MiB idle memory per card,
   readable run journal, and no B70-addressed run-window event.

Any semantic drift, replay drift, malformed/incomplete response, cache use,
mode fallback, compile/capture timeout, memory-admission failure, collective
failure, server exit, or card event stops the arm. A fast quality failure gets
no speed credit. All partial logs and the fresh run directory are retained.

## Bounds and expected time

The launcher admits health for at most 2,700 seconds. The descendant-aware
supervisor bounds the complete lifecycle at 7,200 seconds. The client refuses
to begin with less than 3,900 seconds remaining; the 192-call replay has an
independent 1,800-second bound, each short benchmark row has a 360-second outer
bound and 300-second request bound, and cleanup has finite TERM/KILL grace.

Expected successful wall time is roughly 25-45 minutes on all four cards.
The 120-minute supervisor ceiling is a failure bound, not an occupancy estimate.
The unchanged 192-MiB cache and a single capture size are the lowest-delta first
admission test. XPU graph memory is not fully profiled on this fixed-cache path,
so fit is plausible but not assumed. An admission failure does not authorize an
unregistered cache reduction.

## Prepared invocation

No command below has been run. From the repository root, start the supervisor
by its absolute path, wait for the exact healthy line and live state files, then
invoke the client by its absolute path in a second shell:

```bash
/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-current-piecewise-graph-a1.sh
/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp0-current-piecewise-graph-a1-client.sh
```

Do not launch until a second read-only audit confirms the hashes, path
freshness, current idle state, and lifecycle controls.
