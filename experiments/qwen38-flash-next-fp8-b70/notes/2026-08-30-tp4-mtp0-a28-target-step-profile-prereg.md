# Qwen3.8 Flash-Next FP8 A28 target-step XPU profile preregistration

Date: 2026-08-30
Status: frozen before reboot and GPU launch

## Objective

Measure where the protected TP4 target-only step spends its approximately
181 ms/token before selecting another optimization. A27 showed that a 20%
exact M4 component improvement did not transfer to endpoint throughput. The
separately screened direct reduce-scatter change has only a 1.23 ms/step
best-case projection, below ordinary run variation, and is not an admissible
blind next arm.

## Exact identity

A28 retains the A26 base server identity while explicitly removing A26's
async-PLE selector and restoring synchronous PLE with the default MoE config:

- `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `d14396e27247c1b251da0ce24a0942772c4b002f`, kernels
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, staged build
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager, MTP0, synchronous selective-UVA PLE only, input embedding on
  device, default MoE configuration, max model length 4,352, 128 MiB KV cache,
  prefix cache off, seed and full inherited quality/authority battery;
- attempt 28, port 19700, isolated run/cache/compile/RPC/evidence paths;
- no async-PLE, tuned-MoE, repeatability-trace, graph, speculation, or
  reasoning selector.

The only runtime addition is the existing vLLM PyTorch profiler, with CPU and
XPU activities, shapes on, stack/memory/FLOP capture off, gzip on, and frontend
profiling ignored. It starts after 65 engine iterations and stops after four
profiled iterations. The exact p4096 request is chunked into 64 prefill
iterations, so the captured contexts are the first four pure one-token decode
steps. The first captured context is discarded analytically; the remaining
three are aggregated across ranks. Every measured timing from the profiled
request is permanently ineligible for speed credit.

## Frozen artifacts

- launcher SHA-256
  `492ac0b7cfb0d6f4c64fc2bd1e5ab1ec45222d2dd8ce118f50daeb0dce48f934`;
- profiler CLI wrapper SHA-256
  `b2093aaf3c8cd8310918e019095d34b60c9acaf07d8b9fa5a1f8e577acf9ac15`;
- profile-window helper SHA-256
  `17e5bd6957ce4e94931d06b43fdac3ca5c7906ee410d3080382eda4a5bb025ba`;
- client SHA-256
  `1733790e88afca40409fdfab08d629da6b9e5de4e849dabb897b0fd77625d7cb`;
- supervisor SHA-256
  `4c51385f6cdfa776181ac3ffd9db090f8cb699a5c6ffa989e49cd2672bd27441`;
- offline summarizer SHA-256
  `53620dc6bf658a9bda63b4077a00bfc9710b6856e428116c3ff8237f1abc60a8`.

The raw rank traces are written only to local ext4 under
`/mnt/fast-ai/q38-profiles/attempt28`; the USB evidence drive is not in the
profile write path. The client requires exactly four rank-qualified gzip
traces and four rank tables, binds their hashes in a manifest, and then runs
the unchanged quality, short, and exact-4K battery after profiling has stopped.

## Frozen interpretation

- profiler output is mechanism evidence, never a throughput result;
- one load per boot remains mandatory;
- any request, trace, source, identity, quality, lifecycle, or teardown failure
  closes A28 without changing protected results;
- a noncollective bucket should expose at least 2--3 ms/step, preferably 5 ms,
  before it earns an endpoint treatment;
- collective durations are reported separately because oneCCL device timing is
  not safely additive on this stack;
- if device work does not explain most of the wall interval, the next work is
  host/queue profiling rather than another kernel change.
