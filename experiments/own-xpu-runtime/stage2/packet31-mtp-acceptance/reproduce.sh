#!/usr/bin/env bash
set -euo pipefail
# Invoke this script under nice -n 19 ionice -c 3 from the repository root.
P=experiments/own-xpu-runtime/stage2/packet31-mtp-acceptance
PY=/home/steve/.venvs/vllm-xpu/bin/python
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
nice -n 19 ionice -c 3 "$PY" -B "$P/prepare_target.py"
TMPDIR="$PWD/$P/build" nice -n 19 ionice -c 3 g++ -std=c++20 -O2 -fno-fast-math -ffp-contract=off \
  -shared -fPIC experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/matmul.cpp \
  -o "$P/build/matmul.so"
export OMP_NUM_THREADS=1
nice -n 19 ionice -c 3 "$PY" -B "$P/run_target.py" > "$P/build/runner.log" 2>&1 &
TARGET_PID=$!
trap "kill -TERM $TARGET_PID 2>/dev/null || true" EXIT
nice -n 19 ionice -c 3 "$PY" -B "$P/run_draft.py" > "$P/build/draft.log" 2>&1
wait "$TARGET_PID"
trap - EXIT
nice -n 19 ionice -c 3 "$PY" -B "$P/test_protocol.py" > "$P/test-results.txt" 2>&1
nice -n 19 ionice -c 3 "$PY" -B "$P/analyze.py"
nice -n 19 ionice -c 3 "$PY" -B "$P/finalize.py"
nice -n 19 ionice -c 3 "$PY" -B "$P/archive_receipts.py"
# Inspect results, then invoke cleanup.py to remove only this packet build/.
