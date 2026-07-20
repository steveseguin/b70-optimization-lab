"""Build/load the isolated current-queue command-graph replay shim."""

from __future__ import annotations

import os
from pathlib import Path
from types import ModuleType

from torch.utils.cpp_extension import load


def load_native_replay(build_directory: Path) -> ModuleType:
    source = Path(__file__).resolve().parents[2] / "src/xpu_current_queue_interop.cpp"
    build_directory.mkdir(parents=True, exist_ok=True)
    compiler = os.environ.get("CXX", "")
    if "2025.3" not in compiler or not compiler.endswith("/icpx"):
        raise RuntimeError(
            "CXX must name the oneAPI 2025.3 icpx used by the Torch SYCL 8 stack"
        )
    return load(
        name="option4_current_queue_replay",
        sources=[str(source)],
        build_directory=str(build_directory),
        extra_cflags=["-O2", "-fsycl"],
        extra_ldflags=["-fsycl", "-ltorch_xpu", "-lc10_xpu"],
        verbose=False,
    )
