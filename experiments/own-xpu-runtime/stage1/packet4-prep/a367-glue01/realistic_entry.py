#!/usr/bin/env python3
"""Unchanged timed suite; CPU-only host annotation replaces device discovery."""
import importlib.util
import platform
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]


def main():
    spec = importlib.util.spec_from_file_location('realistic_suite', REPO / 'scripts/bench-openai-realistic-suite.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._measuring_host = lambda: {
        'hostname': platform.node(), 'kernel': platform.release(),
        'gpu_discovery': 'omitted; GPU identity belongs to sealed launch admission',
    }
    return module.main()


if __name__ == '__main__':
    raise SystemExit(main())
