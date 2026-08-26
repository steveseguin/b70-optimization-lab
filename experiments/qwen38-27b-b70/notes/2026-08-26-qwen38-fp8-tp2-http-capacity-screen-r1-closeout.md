# Qwen3.8 official FP8 TP2 active-slot capacity screen R1 closeout

Status: **failed-incomplete harness cleanup classification; p8 diagnostic only**.

R1 launched only p8. Its output gate passed: all responses completed with 128
raw token IDs, every prompt-cache count was zero, and no generated digest
collided with another base task's frozen sequential oracle. The direct p8 point
reached `155.051604 tok/s`, versus the qualified p4 c4 control at
`81.086716 tok/s`. c16-c64 then queued and remained near `155.5 tok/s`.

The frozen runner nevertheless wrote `process-survived` during cleanup. The
detector searched full process arguments for `vllm|qwen38-fp8`, excluded the
runner shell PID, but did not exclude its `timeout` parent. That parent's argv
contained the script filename and produced the false match. Independent
postflight immediately confirmed the container absent, no vLLM/model process,
and port 18089 closed.

The frozen cleanup requirement therefore failed even though the hardware and
service cleanup were actually clean. p16 and p32 were not launched. The p8
rate is useful diagnostic evidence but is excluded from selection and cannot
be published. R2 changes only the process classifier: it parses the PID field
and excludes both the runner and timeout-parent PIDs. It reruns all three
profiles on new fresh servers.

See the [structured closeout](../data/2026-08-26-qwen38-fp8-tp2-http-capacity-screen-r1-closeout.json)
and complete [p8 attempt](../data/qwen38-fp8-tp2-http-capacity-screen-20260826-r1-p8-attempt1/).
