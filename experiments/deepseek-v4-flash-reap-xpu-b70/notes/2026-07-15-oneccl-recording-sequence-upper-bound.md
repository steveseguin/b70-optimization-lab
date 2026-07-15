# oneCCL recording-sequence upper-bound gate

Date: 2026-07-15

## Question

oneCCL's graph-recording LL ring path launches a 16-thread sequence/update
kernel before the BF16 `[4096]` all-reduce kernel. DeepSeek V4 K160 executes 87
of these reductions per decoded token. Before changing oneCCL, price the entire
extra recording-path command stack and require at least `0.50 ms` of headroom
per 87 calls.

## Method

`../scripts/tp4-87-allreduce-recording-gate.py` runs four XCCL ranks and 87
independent BF16 `[4096]` all-reduces per chain. It uses eight warmup chains and
24 measured chains, times the chain with XPU events and host wall time, and
checks the exact BF16 sum after every measured chain on every rank. Tensor reset
and rank barriers are outside the timed interval.

The crossover was:

1. `CCL_SYCL_FORCE_RECORDING_PATH=0`;
2. `CCL_SYCL_FORCE_RECORDING_PATH=1`;
3. `CCL_SYCL_FORCE_RECORDING_PATH=0`.

The forced flag is process-wide. The first harness revision completed its timed
work but its final metadata `all_gather_object` used a non-SYCL collective that
correctly rejected forced graph recording. Result aggregation was changed to
rank-local JSON plus an XCCL barrier, then the forced run was repeated. This did
not change the measured collective path.

## Exact runtime identity

- Python: `/home/steve/.venvs/deepseek-v4-xpu/bin/python`;
- loaded oneCCL: `/home/steve/.venvs/deepseek-v4-xpu/lib/libccl.so.1` and
  `libccl.so.2`;
- `libccl.so.1` SHA-256:
  `ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3`;
- `CCL_SYCL_ALLREDUCE_LL=ring`;
- `CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096`;
- `CCL_TOPO_P2P_ACCESS=1`;
- four B70 devices, recovered after the authorized reboot.

The external `/mnt/usb-models` volume was not mounted after reboot. This did not
alter this A/B or the promoted record runtime: the launcher places the virtual
environment library directory first, and the process maps confirm the venv
oneCCL library above.

## Result

| Path | Max-rank device median / 87 | Max-rank wall median / 87 | Exact |
| --- | ---: | ---: | --- |
| force 0, first control | 5.301166 ms | 5.661933 ms | yes |
| force 1, recording path | 5.383118 ms | 5.795443 ms | yes |
| force 0, reverse control | 5.362058 ms | 5.709612 ms | yes |

Forced recording added `0.081952 ms` against the first control and
`0.021060 ms` against the reverse control. Against the mean of both controls,
the upper bound is `0.051506 ms` per 87 calls, or `0.592 us` per collective.
That is only `10.3%` of the `0.50 ms` integration gate.

Raw evidence:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/recording-path-gate-20260715T025331Z`;
- `../data/recording-path-gate-20260715.json`.

## Decision

Reject sequence/update-to-ring fusion as a speed lane. Even deleting the full
measured forced-path overhead cannot materially move the 34.0671 tok/s record.
The remaining communication work must attack the ring/consumer critical path,
not its small setup kernel.
