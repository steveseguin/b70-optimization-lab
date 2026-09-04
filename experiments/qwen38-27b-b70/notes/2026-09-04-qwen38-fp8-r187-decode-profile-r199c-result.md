# R199c: torch-profiler view of MTP1 decode on the R187 line (TP2, single user)

Date: 2026-09-04 10:01-10:08 EDT, boot 4634e845 (clean). R156 image, `splitting_ops=[]`, MTP depth 1, one request
(prompt ~50 tokens, 8 output tokens) profiled via `--profiler-config '{"profiler":"torch","torch_profiler_dir":…}'`
after a warm request. Traces `…/qwen38-fp8-r187-decode-profile-20260904-r199c/profile/rank{0,1}.*.pt.trace.json.gz`
(11 MB each); rank-0 key-averages table copied to
`data/2026-09-04-qwen38-fp8-r187-decode-profile-r199c-rank0-table.txt`; analyzer
`scripts/analyze-decode-profile-r199.py`. (R199 had no traces: this vLLM ignores `VLLM_TORCH_PROFILER_DIR`;
R199b's 128-token window OOM-killed the workers while serializing under the 12 GB container cap.)

## Device time by kernel family (whole window, rank 0 / rank 1)

| family | rank 0 | rank 1 |
|---|---|---|
| oneCCL all-reduce (`oneccl_allreduce_pcie<half, Rt64_128_PCIE, RingTransmit>`) | 867 ms (66%) | 615 ms (58%) |
| W8A16 GEMM (`gemm_kernel`) | 171 ms (13%) | 171 ms (17%) |
| GDN kernels | 13 ms (1%) | 13 ms |
| norm / elementwise (Inductor Triton) | 6 ms | 6 ms |
| attention (`varlen_fwd`) | 0.8 ms | 0.8 ms |

792 all-reduce calls in the window (128 per target forward: two per layer, 64 layers). Their durations are
bimodal: about 8 µs when both ranks arrive together, medians 776 µs (rank 0) and 9 µs (rank 1), p90 2.5-3 ms,
max 5.9 ms: the collective kernel spins waiting for the peer. The collective runs on its own queue and overlaps
the compute queue, so its time is not additive with compute.

## Busy vs idle (interval union per rank, last quarter of the window = pure decode steps)

| | compute kernels busy | inside a collective | nothing running |
|---|---|---|---|
| rank 0 | 10% | 58% | 32% |
| rank 1 | 10% | 30% | 60% |

Per MTP1 step (35 ms wall) the GPUs execute roughly 3.5 ms of real compute. The rest is the two ranks waiting
for each other inside the collective or sitting idle with nothing queued. GEMM calls: 233 per forward, median
76 µs on device.

## Reading

Single-user decode on this TP2 line is not compute-bound: about 90% of every step is synchronization and
launch latency around 128 small collectives (2 rows x 5120 halves each) and the ~400 custom-op launches per
forward (W8A16 GEMM, GDN, attention, all-reduce). XPU graph replay did not help (R58/R163/R198, size-1 FULL
graph captured but 1.4% slower), and the opaque compiled all-reduce (R60) was neutral, so the cost is not the
launch API itself. The decisive discriminator is the single-card line R206 (TP1: no collectives, twice the
per-card GEMM work): if its decode step is close to TP2's, TP2's advantage is being eaten by collective
synchronization and a device-side one-shot P2P all-reduce (the CUDA `custom_all_reduce` pattern; vLLM's XPU
communicator has no such path, only oneCCL via torch.distributed) becomes the highest-value kernel project on
this lane. The theoretical headroom is large: 3.5 ms of compute per 35 ms step.
