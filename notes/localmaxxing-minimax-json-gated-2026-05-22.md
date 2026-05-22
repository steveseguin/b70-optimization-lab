# LocalMaxxing MiniMax JSON-Gated Submission, 2026-05-22

Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`, AutoRound W4A16 safetensors.

| Label | LocalMaxxing ID | GPUs | Context | Output | tok/s out | tok/s total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `vllm-minimax-m27-autoround-json-gated-c1` | `cmpgv9p9j007qpc01oq5zqhdg` | 4 | 4096 | 2298 accepted | 65.588 | 164.060 |

This is a conservative validation-gated structured JSON result on the promoted fast graph path. The harness delivered `30/30` valid JSON outputs across three deterministic tasks with exact parse/order/arithmetic checks. The submitted `tok/s out` is the effective accepted-output rate including failed attempts and retries. Selected valid outputs alone decoded at `87.770 tok/s`, but raw candidate pass rate was only `30/38` (`78.95%`), so this is evidence for a validator/retry serving pattern, not proof that the raw fast graph path is intrinsically corruption-free.
