import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("verify-q38-a33-fullgraph-runtime.py")
SPEC = importlib.util.spec_from_file_location("q38_a33_runtime", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_graph_stats_accepts_vllm_full_runtime_row() -> None:
    log = """\
**CUDAGraph Stats:**

| Unpadded Tokens | Padded Tokens | Num Paddings | Runtime Mode | Count |
|-----------------|---------------|--------------|--------------|-------|
| 1               | 1             | 0            | FULL         | 37    |
"""
    assert MODULE.graph_stats(log) == [
        {
            "unpadded_tokens": 1,
            "padded_tokens": 1,
            "paddings": 0,
            "runtime_mode": "FULL",
            "count": 37,
        }
    ]


def test_graph_stats_rejects_non_table_text() -> None:
    assert MODULE.graph_stats("CUDAGraphMode.FULL is configured") == []
