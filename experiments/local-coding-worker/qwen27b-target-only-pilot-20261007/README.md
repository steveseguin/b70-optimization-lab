# Target-only 27B worker trial, October 7 UTC

**Closed after healthy runtime gates; coding memory admission refused.**
All eight boundary requests and the actual worker-format canary passed. The
server allocated 9.51 GiB KV per rank (287,232 token capacity) although this
one-sequence trial admits only 33,024 tokens. Host available RAM stayed around
23.5 GiB, below the unchanged 24 GiB task admission. No coding or recall attempt
ran. One SIGINT stopped the application; exit zero, no OOM/kernel fault, idle
render nodes and all four postflight checks passed. See the preserved
[admission](results/task-resource-admission.json) and
[shutdown](results/server/shutdown.json).

A [separately identified smaller-cache arm](../qwen27b-target-only-smallkv-20261007/README.md)
will retain the same model, precision, prompts, context, task budgets and RAM
admission. This original runtime/resource result is not a coding-quality score.

All 80 publisher identities and post-remount cold-copy hashes passed; EX400U is
cleanly unmounted. See the [preservation receipt](model-preservation/summary.json).
This separately identified trial evaluates practical coding and source recall
with the intended 27B model. It does not qualify the published speculative
package, repair R314, or produce a performance headline. The two-card host's
context research, LTX and Flash-Next remain protected.

## Fixed identity and resource admission

Use `Qwen/Qwen3.8-27B-FP8` at
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, all 80 entries in the corrected
[shared manifest](../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json).
Its 66 weight identities remain unchanged. The complete model is
30,890,049,597 bytes; it is staged at
`/dev/shm/qwen38-27b-fp8-worker-20261007` using existing tmpfs, not a new mount
or memory-setting change. The root filesystem keeps its 50 GiB reserve.

The staged model must pass complete SHA-256/Git-blob verification and gain a
verified cold copy on EX400U before any GPU probe. Verify all destination bytes
again after clean unmount/read-only remount, then unmount the external drive.
The supervisor also rehashes every model file immediately before admission.
Model preservation receipts live at
`/home/steve/worker-qwen27b-intake-20261007/model-preservation/`.
This independent publisher copy avoids I/O or endpoint use on the protected
two-card host; the exact local model paths were checked before intake.

The installed R276 image is fixed to
`sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad`.
[Installed-source inspection](runtime-compatibility/README.md) found the required
architecture and block-FP8 route, with no persistent Python-side half-weight
cache along the selected path. This does not measure native scratch allocation,
peak memory or model correctness. No new image pull or native build is planned.

Serve on two of this host's four B70s, TP2/PP1, with FP8 weights, explicit FP16
activations and automatic full-16-bit KV. Context 33,024; block size 64; prefill
batch 512; one sequence; GPU utilization 0.80. Enable the existing
`VLLM_XPU_FP8_BLOCK_W8A16=1` and `VLLM_XPU_GDN_NATIVE_FALLBACK=1` paths.
Row chunk 32; eager execution; no MTP, prefix cache or graph. Other optional
GDN/packed/speculative flags remain explicitly disabled. The full command and
environment are recorded by `serve_r276_once.py` before launching.

Require 64 GiB host memory available **after** model staging. The container's
48 GiB memory and combined memory/swap caps are equal; its 2 GiB `/tmp` and
8 GiB private shared-memory caps count inside that limit. Full CPU task snapshots
need up to about 6 GiB each, one at a time. This is an admission budget, not a
measurement of runtime peak usage. Preserve the existing offline RAM blocks,
power settings, swap and page-cache settings.

TP2 retains the historical OFI/TCP-loopback and pidfd descriptor exchange.
A CPU-only sibling descriptor probe showed that Docker's non-root process lost
effective SYS_PTRACE and was refused. Container UID 0 with **only SYS_PTRACE**
passed under default seccomp and no-new-privileges. The supervisor binds that
[receipt](communication-admission.json) to the exact image and probe source.
It uses private PID/IPC namespaces and a read-only root/model, with no host
filesystem access beyond model and GPU-device metadata. This CPU check does
not qualify GPU collectives.

## Restricted runtime gate

MTP disabled avoids the later-discovered speculative state-width transition.
R276 still predates the separate one-token-prefill fix. Every admitted prompt
must contain more than one total token; the unchanged worker SYSTEM plus a tiny
user message already counts 331 tokens. No general fix is claimed.

Before useful tasks, run [the frozen boundary diagnostic](boundary-protocol.json):
511, 513, 512 and 1,025 total input tokens, then the same sequence again. All
must return the fixed marker, have exact tokenizer/usage agreement, complete
output-token identities, natural stop and explicit zero cache. Repeated
identical prompts must produce identical token IDs. The gate has 300 seconds
total and no retries. This detects a finite set of marker/repeat failures; it
is **not** a full arithmetic oracle or proof of unchanged-model equivalence.

Then run one no-execution canary with the actual unchanged worker SYSTEM and
frozen profile. Require a valid simple command printing `pilot-ok` and complete
transport/accounting receipts. Failure closes this attempt and requests one
graceful shutdown; it never starts another server.

## Coding and recall sequence

Use the frozen [evaluation tasks](../evaluation-20261007/README.md), in order:

1. `lab-catalog-pending-headlines`
2. `lab-context-number-boundaries`

One attempt each, 40 model steps, 20 minutes, 28,000 input tokens, 2,048 output
tokens and three acceptance attempts. Preserve the original SYSTEM; do not add
path hints learned from the 4B failures. These tasks were observed in the 4B
trial, but no 27B response has been seen. Report the 27B profile separately;
different model, quantization, runtime and budgets prevent a matched comparison.

Keep the real complete historical source snapshots. After each task, stop its
CPU sandbox, independently review any patch, bind the review to exact identities,
freeze-check and verify a durable evidence archive, fsync it, then remove only
its own disposable RAM snapshot. Keep the source repository clean throughout
the task and export. No automatic merge or hints/reruns. Ordinary task failure
does not restart the model server.

After both attempts, reuse the healthy server for one full-corpus recall
request if at least eight minutes remain. The five documents and all ten
questions are unchanged from the earlier refused prompt. CPU tokenization
counts 14,008 input tokens; recheck against the actual endpoint. Reserve 4,096
answer tokens within 33,024 context, with a 420-second total network budget.
No source truncation, answer key, retry, answer repair or extra context is
allowed. Validate exact citations and review semantics separately. This remains
a curated reading baseline, not million-token memory qualification.

One supervised server, at most 60 minutes total. It holds the host/device locks,
watches faults/OOM, uses a single SIGINT for graceful shutdown, waits for owned
container exit and render-node idleness, and performs healthy-only four-card
postflight. It never escalates to a hard kill, resets a driver or reboots.
Stop it immediately after the planned sequence; preserve every failed result.

Durable output root: `/home/steve/worker-qwen27b-pilot-20261007/`.
Entry points: `serve_r276_once.py --out ROOT/server`,
`check_boundaries.py --out ROOT/boundaries --server-state ROOT/server`,
`check_transport.py --out ROOT/transport-canary --server-state ROOT/server`,
`run-task.py TASK`, then `run-memory.py`. The orchestrator owns sequencing,
archive/review, and the final `ROOT/server/STOP` file.
