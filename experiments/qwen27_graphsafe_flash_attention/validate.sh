#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_tree=${1:-/home/steve/src/vllm-xpu-kernels}
target=csrc/xpu/attn/xe_2/chunk_prefill.hpp
patch_file=$here/qwen27-chunk-prefill-local-accessor.patch

test -f "$source_tree/$target"
git -C "$source_tree" apply --check "$patch_file"

python3 -m py_compile "$here/test_graph_replay.py"
bash -n "$here/build.sh"

python3 - "$patch_file" "$here/test_graph_replay.py" <<'PY'
from pathlib import Path
import sys

patch = Path(sys.argv[1]).read_text()
probe = Path(sys.argv[2]).read_text()

required_patch = (
    "sycl::local_accessor<SharedStorage, 1>",
    "syclex::sub_group_size<16>",
    "intelex::grf_size<256>",
    "FMHAKernel{}(params, scratch_ptr)",
)
for marker in required_patch:
    assert marker in patch, f"missing patch invariant: {marker}"
assert "+        syclex::work_group_scratch_size" not in patch

required_probe = (
    "ROWS = 4",
    "Q_HEADS = 12",
    "KV_HEADS = 2",
    "HEAD_DIM = 256",
    "KV_LENGTHS = (128, 1024, 2048)",
    "MIN_REPLAYS = 1000",
    "torch.float16",
    "torch.xpu.XPUGraph()",
    "block_table=block_table",
    "seqused_k=seqused_k",
    "graph_out.fill_(float(\"nan\"))",
)
for marker in required_probe:
    assert marker in probe, f"missing test invariant: {marker}"
PY

printf 'PASS: patch applies and graph-safe launch/test invariants are encoded.\n'
