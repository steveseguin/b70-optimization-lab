# First-token correctness investigation, October 11

The alleged bad generated sequence was **prompt input**, not generated output.
[`input-audit.json`](input-audit.json) records the observation time, exact IDs,
rendered chat template, oracle text, and available device coverage. The live
device window is read-only throughout this work. See the
[investigation note](../../../../../notes/2026-10-11-first-token-correctness.md).
[Closeout and remaining device check](CLOSEOUT.md).

`host_check.cpp` includes the unchanged Packet 13 program and executes its
host-only `Engine`, loader, operators and arithmetic selector. A prefix check
omits later layers and the output head while keeping the position commit.
The full check keeps all 48 layers and runs the head at the last prompt
position. Intermediate prompt-position head predictions are unused and are
skipped; prompt token IDs are always supplied explicitly. It independently
checks the final finite-logit argmax with the same lowest-ID tie rule.

The builder also compiles the **unmodified** Packet 13 CLI. Its fresh layer-0
result is retained under `original-layer0/`; the two-layer harness result is
under `prefix2/`. Both preserve the original layer-0 bytes. The parallel CPU
overlay adds only an OpenMP loop over independent GEMV output rows; no row's
reduction, BF16 boundary, weight or nonlinear function changes. All fixture
files use `[1,4,2560]`, little-endian BF16 and the original JSONL hash format.

[`full48/receipt.json`](full48/receipt.json) completes 87 positions through
48 layers in 492.112819 seconds, peak RSS 897,220 KiB. The first predicted
token is 332 (`**`), and the independently checked argmax agrees.
[All 48 hashes match](runtime-order-oracle-comparison.json) the runtime-order
CPU oracle's retained step 1; [device comparison](device-comparison.json)
has zero available native fixtures and is pending. This is CPU execution
agreement under shared math, not device qualification. The two-layer fresh
repeat is [also exact](prefix2-repeat.json).

`build.json` binds the numeric runs. `host_check-run.cpp.txt` preserves the
exact original harness source matching that build: during review its failure
path was fixed to preserve an existing output directory on refusal. The fix
changes no numerical operation. `build-final.json` binds the corrected source.
Both builds are host-only and have checked dynamic dependencies. Numerical
processes use nice 19, eight OpenMP threads and a 38 GB address-space cap;
the original CLI uses two threads and an equivalent shell address cap.
Weights are read-only and streamed, with no full-model host shadow.

## CPU reproduction

Run from the repository root. Supply a **new** scratch directory; the builder
does not touch Packet 13's protected `build/`. The prepared input directory is
read-only. To reproduce without that directory, use Packet 13 `prepare.py`
with a separate new output directory at nice 19, ionice class 3 and OMP=2.

```bash
P=experiments/own-xpu-runtime/stage2/packet13-integrate
S=/tmp/iq3-first-token-NEW
PY=/home/steve/.venvs/vllm-xpu/bin/python
nice -n 19 env OMP_NUM_THREADS=2 "$PY" -B "$P/correctness/build_host.py" "$S" "$S-receipt.json"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=8 "$S/host-check" \
  "$P/build/input" "$S/prefix2" \
  /mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS 2 5400
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=8 "$S/host-check" \
  "$P/build/input" "$S/full48" \
  /mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS 48 5100
nice -n 19 env OMP_NUM_THREADS=2 "$PY" -B "$P/correctness/compare_layers.py" \
  "$S/full48/step1" "$P/build/card3-first-token-a/run/step1" "$S/comparison.json" 48
```

Retain the receipts, positions and fixture files before deleting your scratch.
The 5,100-second full-pass guard plus the measured prefix checks fits the
requested 90-minute numerical budget. A stopped pass remains partial.
No automatic restart or GPU command is part of this procedure.

`inspect_run.py OUTPUT` snapshots only complete timing rows, the input,
existing output records and fixtures. It decodes with the oracle's `Tokenizer`
constructed from the GGUF header metadata (that class takes metadata, not a
file path). `test_inspect_run.py` tests the prompt/output distinction;
`test_compare_layers.py` tests missing, partial, matching and divergent fixture
coverage. Run both with the same Python at nice 19, OMP=2 and `-B`.
`cpu-tests.json` retains the original CLI's 13 integration cases.

Missing native fixtures cannot establish a matching or divergent operator.
BLAS-order comparisons are numerical diagnostics, not an exactness gate for
the frozen runtime order. A small difference likewise does not certify the
model. Device/full-model repeats and independent quality gates remain open.
