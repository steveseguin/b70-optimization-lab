#!/home/steve/.venvs/vllm-xpu/bin/python
"""Exec the pinned vLLM CLI with the frozen A28 report-only profiler config."""

import json
import os
import sys


REAL_VLLM = "/home/steve/.venvs/vllm-xpu/bin/vllm"
PROFILE_DIR = "/mnt/fast-ai/q38-profiles/attempt28"
PROFILE_CONFIG = {
    "profiler": "torch",
    "torch_profiler_dir": PROFILE_DIR,
    "torch_profiler_with_stack": False,
    "torch_profiler_with_flops": False,
    "torch_profiler_use_gzip": True,
    "torch_profiler_dump_cuda_time_total": True,
    "torch_profiler_record_shapes": True,
    "torch_profiler_with_memory": False,
    "capture_torch_profiler": False,
    "detailed_trace_annotation": False,
    "ignore_frontend": True,
    "delay_iterations": 65,
    "max_iterations": 4,
    "warmup_iterations": 0,
    "active_iterations": 5,
    "wait_iterations": 0,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] != "serve":
        raise SystemExit("A28 wrapper accepts only the vLLM serve command")
    if os.environ.get("Q38_A28_PROFILE_DIR") != PROFILE_DIR:
        raise SystemExit("A28 profile directory identity is absent or changed")
    if "--profiler-config" in sys.argv[2:]:
        raise SystemExit("A28 refuses an existing profiler configuration")
    config = json.dumps(PROFILE_CONFIG, sort_keys=True, separators=(",", ":"))
    os.execv(REAL_VLLM, [REAL_VLLM, *sys.argv[1:], "--profiler-config", config])


if __name__ == "__main__":
    main()
