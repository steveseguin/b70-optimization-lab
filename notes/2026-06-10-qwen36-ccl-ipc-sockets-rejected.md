# Qwen3.6 CCL IPC Sockets Rejected

Date: 2026-06-10

## Candidate

Tested a math-preserving communication runtime change:

- `CCL_ZE_IPC_EXCHANGE=sockets`

The accepted service leaves `CCL_ZE_IPC_EXCHANGE` unset/default. Everything
else stayed aligned with the accepted Qwen3.6 runtime:

- Quark W8A8 INT8 checkpoint
- TP4, 32K context, no prefix caching
- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- clone-safe custom-op all-reduce
- PIECEWISE XPU graph
- max batched tokens `8192`
- max seqs `48`

Rationale: the live accepted rank-0 graph has `162` `torch.ops.vllm.all_reduce`
calls, so CCL IPC setup is a low-risk place to check for latency movement
without changing model math.

## Artifacts

Fresh accepted control:

- `data/qwen36-quark-int8-tp4-noprefix-current-control-cclipc-20260610.json`

Candidate:

- `data/qwen36-quark-int8-tp4-noprefix-cclipc-sockets-single-r8-20260610.json`

Runtime log:

- `/tmp/qwen36-quark-int8-tp4-cclipc-sockets-32k-noprefix-20260610.log`

## Speed Gate

Both runs used the standard p512/n512, 8-repeat, streaming speed gate.

| run | corrected after-first tok/s | e2e tok/s | total tok/s | TTFT ms | vLLM e2e ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| accepted default IPC | `99.6577` | `98.4025` | `196.8049` | `75.604` | `5202.126` |
| `CCL_ZE_IPC_EXCHANGE=sockets` | `98.4072` | `97.2178` | `194.4356` | `73.803` | `5267.680` |

## Decision

Reject. `CCL_ZE_IPC_EXCHANGE=sockets` regressed single-request decode speed by
about `1.25 tok/s` corrected after-first and `1.18 tok/s` e2e. No quality suite
was run because the candidate failed the speed gate.

The accepted default IPC service was restored:

- tmux session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- backend `/health`: pass
- frontdoor `/v1/models`: pass

## Lesson

For this Qwen3.6 TP4 32K graph stack, the default Level Zero IPC exchange is
better than forcing sockets. Keep `CCL_ZE_IPC_EXCHANGE` unset in the accepted
runtime.
