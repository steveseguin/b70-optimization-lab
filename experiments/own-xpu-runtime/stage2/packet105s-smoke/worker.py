#!/usr/bin/env python3
"""Private v4 worker with only the first 64-token request retained."""
import argparse
from pathlib import Path
from smoke import verify_adapter, load_adapter, CHOICE, PROMPT


def main():
    pins = verify_adapter()
    from common import read, require
    from conditions import lane_gate
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, required=True)
    args = parser.parse_args()
    identity = read(args.identity)
    require(identity['lane'] == 'B' and identity['smoke'] == dict(
        prompt_id=PROMPT, generated_tokens=64, request_count=1,
        candidate=CHOICE, adapter_sources=pins), 'smoke identity changed')
    lane_gate('B')
    require((args.identity.parent / 'window.json').is_file(), 'outer screen admission required')
    return load_adapter('tp2_worker.py').run(identity, args.output, args.seconds)


if __name__ == '__main__':
    raise SystemExit(main())
