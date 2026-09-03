# Qwen3.8 Flash-Next FP8 A67 full-decode-graph deterministic-oneDNN result

Date: 2026-09-02 21:31--21:50 EDT
Status: diagnostic positive as far as it ran; terminated by the supervisor's
bounded root-NVMe read guard, not by a hang or fault; no promotion claim

## Outcome

A67 (the frozen A59/A56 full-decode-graph server: `VLLM_XPU_ENABLE_XPU_GRAPH=1`,
public oneCCL `4ceafd1` with twoshots, tuned M1 W13-N32 map, PLE-only UVA
placement, 2304 max model length) ran overlay head `805cde59...` with
`VLLM_XPU_MKLDNN_DETERMINISTIC=1`; four `mkldnn.deterministic=True` lines
appear in the server log. Load took 13 minutes (weights 21:42, healthy
21:46, graph captured).

| depth | first-step logits identical (8x) | spread | 128-token repeats |
| --- | --- | --- | --- |
| 8 | yes | 0.0 | 3/3 identical, zero logprob difference |
| 64 | yes | 0.0 | 3/3 identical, zero logprob difference |
| 256 | yes | 0.0 | not reached |
| 2048 | not reached | | |

At 21:49:33, during the first 128-token repeat at depth 256, the supervisor
sent SIGTERM: its per-second guard requires cumulative root-NVMe reads since
its baseline to stay under 16,777,216 sectors (8 GiB), and the sample at
that second read 16,785,984. The workers shut down in order, the engine
reported a fatal error, the probe saw HTTP 500, and teardown completed with
final status 70 and the failure file `FAIL A67 final host-pressure or
NVMe-link guard`. NVMe and root-port AER counters were 0 throughout; no
kernel GPU or PCIe event; four cards discoverable after teardown.

The read volume is not a storage fault. The runtime trees had been
pre-read into the page cache (13.9 GiB in 4 s) before launch, yet the
host-pressure log shows about 3.4 GiB of root-NVMe reads per minute while
requests were served with 24 GiB available and the server holding about 100
GiB of host memory: mapped runtime pages are reclaimed and re-faulted under
that pressure. A66 (eager) crossed the same cap only at its postflight.

## Reading

Nothing in A67 contradicts A66: with the deterministic oneDNN flag the graph
line is logit-exact at every point measured (first steps at 8, 64 and 256
tokens; 128-token repeats at 8 and 64). The bounded-read guard dates from
the Samsung link investigation and is now stricter than the host's state
allows; the AER guard (at most 64 corrected events per run, zero seen since
BIOS 2.4a) remains the storage-health gate.

## Next

A68: the same server with the bounded-read cap raised from 16,777,216 to
134,217,728 sectors (64 GiB) in the launcher pre-check and the supervisor
guard, AER guard unchanged, running the frozen client battery (recovery
canary, 7 exact semantic cases, 16-repeat, exact 2K needle, short rows,
exact-2K rows) instead of the probe.
