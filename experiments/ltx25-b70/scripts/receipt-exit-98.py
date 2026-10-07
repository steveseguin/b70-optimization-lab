#!/usr/bin/env python3
"""Map only explicit memory refusals to does-not-fit; read no devices or weights."""
import json
from pathlib import Path
import sys


def failure_code(path, fallback):
    try:
        receipt = json.loads(Path(path).read_text())
        if receipt.get('outcome') in ('insufficient-memory', 'memory-floor', 'chain-check-no-room'):
            return 18
    except (OSError, ValueError, AttributeError):
        pass
    return fallback


if __name__ == '__main__':
    print(failure_code(sys.argv[1], int(sys.argv[2])))
