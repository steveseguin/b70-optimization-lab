# Qwen3.6 Q4_0 TP1 target-only exact-depth preregistration

Date: 2026-08-25. State: **preregistered; not launched**.

This packet measures the seven exact active-context depths `0`, `2048`,
`4096`, `8192`, `16384`, `24576`, and `32768` for one matrix identity:

- Qwen3.6 27B weights, Unsloth MTP-bearing Q4_0 GGUF child;
- one B70, llama.cpp/SYCL build 9976, target-only MTP0;
- XPU graph explicitly off, q8_0 K/V cache, FlashAttention on;
- raw `llama-bench` `tg128` decode plus its `pp2048` rows.

The exact command is frozen in the campaign manifest. It uses
`-dev SYCL0 -ngl 99 -sm layer -p 2048 -n 128`, the complete seven-value
`-d` list, `-b 2048 -ub 512 -fa on -ctk q8_0 -ctv q8_0 -t 16 --poll 50
-r 5 -o json`. No speculative arguments are present. Although the GGUF has
embedded MTP tensors, this packet measures only its unchanged target path.

## Identity and lifecycle gates

The model is fixed at 16,056,476,800 bytes and SHA-256
`20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a`.
The original Hugging Face repository revision was not captured. The sibling
Q4_K_M file's `5cb35e...` revision is not inherited or guessed; this artifact
is explicitly checksum-pinned.

The launcher binds the exact `llama-bench` SHA-256
`90d4d23363825219d6cff02d59b73c3912fd42071694e8e215ba8cfc5d058aff`,
the implementation library SHA-256
`f963fc1504afeff14bdd389f65a00d9b581e40056bef0c9b81e17e89fc0d79d5`,
and every effective shared library resolved under the frozen oneAPI 2026.0
library path. The source tree was dirty when build 9976 was produced, so the
binary and DSO hashes, not the current mutable source checkout, are the
runnable identity.

Execution requires the exact acknowledgement, a clean `main` equal to the
live `origin/main` ref, the canonical Muse/host/GPU0 locks, an idle host with
no model process, container, or render-node owner, and a create-only run root
on ext4. Inherited `GGML_*`, `LLAMA_*`, SYCL/Level-Zero/oneAPI, OpenMP/MKL,
and library-path controls are rejected. The launcher supplies the complete
controlled environment itself and requires the runtime log to attest
`GGML_SYCL_ENABLE_GRAPH: 0` and `GGML_SYCL_GRAPH_CACHE_SIZE: 0`.

The raw JSON and metadata are converted only through
`scripts/parse-llama-bench-exact-depth.py`. Any binary, model, library,
argument, environment, graph marker, row-shape, filesystem, Git, lock, idle,
parser, or receipt failure leaves the cells unfilled. A created run root is
never reused or overwritten and always receives a terminal pass/fail receipt.

## Evidence boundary

This is a raw-engine benchmark, not an HTTP serving measurement, and it does
not run a quality battery. Historical same-artifact target-only evidence at
`data/qwen27-cycle-timeline/no-spec-normal-20260712T160033Z/qwen27-q4_0-kv8-no-spec-graph0-strict128-20260712T160033Z.json`
passed its separate 12-prompt fresh-response/cache-zero gate. That historical
quality statement is supporting context only; it is not transferred to the
new context cells.

There is no speed floor. No speed or quality transfers from Q4_K_M,
UD-Q4_K_XL, Q8_0, AutoRound, another runtime build, MTP-bearing speculation,
or another context depth. A passing packet adds seven measurements under this
exact identity and cannot lower or overwrite any prior captured result.
