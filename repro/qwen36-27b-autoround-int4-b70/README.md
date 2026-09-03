# Qwen3.6 27B AutoRound INT4 TP2 — 95.385 tok/s repro

> **Certification: `candidate-portable-repro`, not a starter guide.** Install,
> restore, launch, and validation material is closed for the lab's own hosts;
> clean-host certification is still pending. The open items are listed under
> this guide's `missing` entry in [`repro/guide-catalog.json`](../guide-catalog.json).

This is the standalone reproduction packet for the historical two-B70
Qwen3.6 27B **AutoRound INT4** vLLM/XPU record:

| Field | Record identity |
| --- | --- |
| Model | [`webhie/Qwen3.6-27B-int4-AutoRound`](https://huggingface.co/webhie/Qwen3.6-27B-int4-AutoRound/tree/f5750c90b3776db658594df5fe8051098226dd8e) |
| Revision | `f5750c90b3776db658594df5fe8051098226dd8e` |
| Quantization | AutoRound INT4 W4A16, group 128, symmetric |
| Runtime | private record vLLM/XPU source, PyTorch `2.11.0+xpu`, Intel oneAPI 2025.3 |
| Hardware | 2x Intel Arc Pro B70 32 GB, TP2, concurrency 1 |
| Speculation | intrinsic target-verified MTP3 with exact ReplaySSM state |
| Headline | **`95.384867741895 tok/s`** median, p10 `86.975415`, mean `95.623050` |
| Quality | exact cases, repeat128, baseline parity, and 1K needle passed |
| Freshness | 12 unique prompts once each, all `cached_tokens=0`, no reuse |
| LocalMaxxing | approved record `cmrh35ct50092mj01h7jgydqj` |

This packet exists because the exact record commits were local-only and the
working implementation also contained uncommitted source. Both are now
preserved as small Git bundles plus exact working patches.

## 2026-08-15 independent revalidation

The historical packet reconstructs the July result, but a newer
contribution-style validation now provides the stronger current classification:

- six fresh servers across both physical two-GPU pairs;
- two target-only controls and four speculative arms;
- 12 historical prompts plus 13 later mixed-task holdouts, every prompt once;
- 512-token caps, zero cached tokens, and conventional 99-interval accounting;
- exact cases, repeat32, baseline parity, and 1K retrieval on every arm.

All arms and objective quality gates passed. The median of the four
speculative combined medians was **98.766 tok/s** (arm range
98.353–101.078; prompt-bootstrap 95% interval 92.969–104.754). On the old
12-prompt family alone it was **94.689 tok/s**, closely reproducing the
historical result after correcting the interval accounting. The matching
target-only controls were 47.868 and 48.006 tok/s.

However, all four speculative arms differed from their target-only controls on
25/25 realistic prompts, and fresh same-pair restarts differed on 19/25 and
21/25 prompts. The preregistered strict result is therefore **fail**:
throughput and narrow objective quality reproduce, but target-only token parity
and fresh-start output determinism do not. The result is not a robust `>100`
claim and was not submitted as a new LocalMaxxing record.

Plan, harness, full compact evidence, raw-root checksum, and analysis:
[`../../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md`](../../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md).
The July LocalMaxxing row remains a historical record under its original
metric and quality standard; it should not be read as passing this later,
stricter parity standard.

## Identity boundary: this is not the Q8 result

Do not combine this packet with the Qwen GGUF Q8 work. They are different
model/runtime identities:

- **this packet:** AutoRound INT4 W4A16 checkpoint, vLLM/XPU, target-verified
  MTP3, two B70s, `95.385 tok/s` under the July 2026 historical metric;
- **Q8 TP2 packet:** Q8_0 GGUF, llama.cpp/SYCL, target-only/no-speculation,
  two ASRock B70s, `35.699 tok/s` under conventional accounting.

The Q8 packet is at
[`../qwen36-27b-q8-tp2-asrock-b70/README.md`](../qwen36-27b-q8-tp2-asrock-b70/README.md).
Neither result is evidence for the other.

## What is preserved

The packet is intentionally layered so a reviewer can audit it without a GPU
and a reproducer can rebuild it without access to the original private Git
refs.

- [`manifests/model.json`](manifests/model.json): exact Hugging Face revision,
  file sizes, LFS SHA256s, and Git blob IDs.
- [`manifests/runtime.json`](manifests/runtime.json): OS, compiler, Python,
  PyTorch, source, oneCCL, and binary identities.
- [`manifests/expected-result.json`](manifests/expected-result.json): exact
  metric, quality, crossover, and LocalMaxxing expectations.
- [`configs/record.env`](configs/record.env): the complete positive runtime
  configuration, including graph and ReplaySSM flags.
- [`evidence/`](evidence/): tracked strict/quality/crossover JSON plus a
  deterministic archive of the original isolated and crossover run
  directories, including server logs, source snapshots, runtime binary
  hashes, and per-run identities.
- [`../../patches/qwen36-27b-autoround-int4-b70/record-20260711/`](../../patches/qwen36-27b-autoround-int4-b70/record-20260711/): public
  prerequisite pins, private commit bundles, and exact dirty patches.
- [`realistic-suite-v1.json`](realistic-suite-v1.json) and
  [`long-context-suite-v1.json`](long-context-suite-v1.json): frozen suites.
- [`HISTORICAL_RECIPES.md`](HISTORICAL_RECIPES.md): the superseded TP1 and
  earlier TP2 recipes that previously occupied this README. They are retained
  for research history, not discarded or silently rewritten.

The generated XPU libraries are too large for Git. Their exact record hashes
are preserved in
[`evidence/xpu-runtime-binaries.sha256`](evidence/xpu-runtime-binaries.sha256),
and the source/build path below reconstructs them. The public oneCCL build is
also reconstructed from pinned source; its deployed library and `kernels.spv`
must match the recorded hashes before the run wrapper will start.

The benchmark/research repository itself was clean at public commit
[`ac5110e139267e90097d6c207fb24141c2bb0af0`](https://github.com/steveseguin/b70-optimization-lab/commit/ac5110e139267e90097d6c207fb24141c2bb0af0).
The original launcher and server snapshots are inside the evidence archive.
The promoted wrapper in this packet reconstructs the two final transaction
flags from the recorded `identity.env` and adds only portability, source
identity, output-overwrite, and benchmark-lock checks.

## 1. Verify the packet without GPUs

From the repository root:

```bash
python3 repro/qwen36-27b-autoround-int4-b70/scripts/verify-packet.py
```

This checks packet/source checksums, parses all JSON, asserts the strict and
quality gates, verifies both crossover windows, reads every archived file and
matches it to the uncompressed archive manifest, and inspects both Git
bundles. It does not initialize a GPU.

## 2. Restore the exact source

The restore is intentionally detached: it creates no working branch.

```bash
cd /path/to/llm-optimizations
repro/qwen36-27b-autoround-int4-b70/scripts/restore-source.sh \
  /path/to/qwen27-int4-record-source
```

The result is:

```text
/path/to/qwen27-int4-record-source/
├── vllm/              # detached e7213ba8... + exact dirty patch
└── vllm-xpu-kernels/  # detached 3b4effee... + exact dirty patch
```

The script starts from public prerequisites, fetches the private continuation
from the tracked bundles, applies the recorded patches, and requires the final
`git diff --binary` hashes to be exactly:

- vLLM: `dcf84454f64bdeca546aa1697f4cd6af89fa95bb56f80ed314ad4d364e134b24`;
- kernels: `edcb9314b43d6990474dfb5d64e3716e8d4c33618ec0e3fbd11ae671e47c8c1f`.

The underlying public anchors are linked in the
[source packet README](../../patches/qwen36-27b-autoround-int4-b70/record-20260711/README.md).

## 3. Download and verify the model

The model is about 19.0 GB. The helper reads an optional Hugging Face token
from `~/.config/huggingface/token` without printing it.

```bash
HF_HOME=/path/to/hf-cache \
  repro/qwen36-27b-autoround-int4-b70/scripts/download-model.sh
```

To verify an existing snapshot without downloading:

```bash
MODEL_DIR=/path/to/f5750c90b3776db658594df5fe8051098226dd8e \
  repro/qwen36-27b-autoround-int4-b70/scripts/download-model.sh
```

All nine LFS payloads are checked by SHA256; the remaining small files are
checked by Git blob identity. The helper prints the verified snapshot path.

## 4. Match the runtime family

The record used:

- Python 3.12;
- PyTorch `2.11.0+xpu`;
- Triton XPU `3.7.0`;
- Intel oneAPI compiler `2025.3` (`IntelLLVM 2025.3.3` for oneCCL);
- the `libsycl.so.8` runtime family supplied with that stack;
- Ubuntu 24.04-family userspace and kernel `6.17.0-35-generic`;
- a Level Zero driver reporting numeric version `17012132`.

Do not source the oneAPI 2026 umbrella environment for an exact replay. A
PyTorch 2.13/SYCL 2026 port may be worthwhile, but it is a new runtime
identity and must be validated separately.

Build the restored source and the staged graph-safe FlashAttention package:

```bash
SOURCE_ROOT=/path/to/qwen27-int4-record-source \
VENV=/path/to/venvs/qwen27-int4-record \
MAX_JOBS=8 \
  repro/qwen36-27b-autoround-int4-b70/scripts/build-runtime.sh
```

The build helper installs the source XPU kernels and vLLM editable, then uses
the existing isolated graph-safe FlashAttention builder to apply:

- `qwen27-chunk-prefill-local-accessor.patch`;
- `qwen27-force-chunk-decode.patch`.

It never modifies the restored kernel checkout. A successful build prints the
staged package path. Record binary hashes are expectations for the historical
artifacts, not a promise that a rebuilt ELF will be byte-identical across
hosts; source identity and the runtime gates are authoritative for a rebuild.

## 5. Build and verify pinned oneCCL

Installed oneCCL `Gold-2021.17.2` failed the packed verifier's exact command-
graph oracle. The record used public oneCCL parent `b52f40c...`, libccl
`4ceafd1...`, built with Intel 2025.3:

```bash
ONECCL_INSTALL_DIR=/path/to/oneccl-4ceafd1-b70 \
  experiments/qwen36-27b-autoround-int4-b70/oneccl_ll256/build-public-oneccl.sh
```

Required outputs:

```text
43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700  lib/libccl.so.1.0
0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9  lib/ccl/kernels/kernels.spv
```

The run wrapper refuses any other hashes. Before benchmarking a rebuilt host,
also run the all-reduce and all-gather graph oracles documented in
[`../../experiments/qwen36-27b-autoround-int4-b70/oneccl_ll256/README.md`](../../experiments/qwen36-27b-autoround-int4-b70/oneccl_ll256/README.md).

## 6. Run the exact gate

Stop other GPU services first. The helper takes a nonblocking shared benchmark
lock and refuses an existing output directory. Physical GPUs may be any pair;
inside the narrowed visibility set they are addressed as logical devices 0,1.

```bash
SOURCE_ROOT=/path/to/qwen27-int4-record-source \
MODEL_DIR=/path/to/f5750c90b3776db658594df5fe8051098226dd8e \
VENV=/path/to/venvs/qwen27-int4-record \
STAGE=/path/to/llm-optimizations/experiments/qwen27_graphsafe_flash_attention/work/source \
ONECCL_INSTALL_DIR=/path/to/oneccl-4ceafd1-b70 \
GPU_INDEX=0,1 \
PORT=19622 \
RUN_ROOT=/path/to/results/qwen27-int4-repro \
  repro/qwen36-27b-autoround-int4-b70/scripts/run-record.sh
```

The wrapper:

- validates both detached source heads and both dirty patch hashes;
- validates oneCCL and `kernels.spv` byte hashes;
- clears inherited Qwen/vLLM/XPU/CCL experiment variables;
- loads [`configs/record.env`](configs/record.env);
- snapshots the selected source and all runtime XPU binaries;
- starts one isolated TP2 server;
- runs smoke, the 12-prompt strict fresh suite at 512 output tokens, and the
  repeat128/1K quality suite;
- stops the server through the existing cleanup trap and preserves a unique
  run directory.

Expected endpoint identity includes:

- target dtype FP16 over the AutoRound INT4 checkpoint;
- runtime INT8 target LM head with BF16 scales;
- runtime INT4 group-128 draft LM head with BF16 scales;
- MTP3, ReplaySSM cache length 8, commit in forward, and conservative PyTorch
  slot management;
- `FULL_AND_PIECEWISE` with capture size 4;
- graph-safe forced chunk decode and one full target graph;
- compiled all-gather custom-op boundary;
- exact pending-metadata and direct-core-output transaction fusions;
- no prefix caching, no history reuse, thinking disabled, temperature-zero
  deterministic quality requests.

## Interpreting a reproduction

The historical primary field is named
`median_tok_s_1_100_after_ttft`. It is preserved exactly as emitted in July
2026. The repository later standardized a separate conventional 99-interval
policy, so do not silently relabel this historical number. Compare a new run
using the packet's own field first, then report any newer accounting as an
additional metric.

Passing reproduction requires more than a throughput value:

- all 12 strict prompts unique and run once;
- all `cached_tokens=0`;
- target-verified MTP3 active;
- exact cases, repeat128, baseline parity, and 1K needle all passing;
- no model/source/runtime identity drift;
- no use of the Q8/Q4 model or llama.cpp path.

The record was short-context optimized. Forced chunk decode scales poorly at
long context, so this packet does not claim a deployable 32K service. The
separate service ladder and earlier variants remain in
[`HISTORICAL_RECIPES.md`](HISTORICAL_RECIPES.md).

## Evidence and provenance

- promoted result:
  [`../../results/qwen36-27b-autoround-int4-b70/tp2-fp16-fullgraph-transaction-20260711.json`](../../results/qwen36-27b-autoround-int4-b70/tp2-fp16-fullgraph-transaction-20260711.json)
- decision note:
  [`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-11-fullgraph-transaction-record.md`](../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-11-fullgraph-transaction-record.md)
- original community request:
  [GitHub Discussion #29](https://github.com/steveseguin/b70-optimization-lab/discussions/29)
- LocalMaxxing approval: `cmrh35ct50092mj01h7jgydqj`

Packet verification checks source reconstruction and retained evidence without
using GPUs. A new throughput claim still requires the live command above on a
matching two-B70 host.
