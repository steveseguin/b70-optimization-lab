#!/usr/bin/env python3
"""Check native parser limits; every case must refuse before device authorization."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    common = ['--rank', '0', '--gsq-packed', '--recurrent-f32',
              '--attention-q8-p33', '--qkv-q6-p33', '--activations', 'f32',
              '--memory', 'resident', '--context', '4096', '--output',
              '/dev/shm/ownrt-parser-refusal-must-not-create']
    pipeline = ['--pipeline-stage', '0', '--pipeline-boundaries', '0,13,25,37,48']
    cases = [('pipeline512', common+pipeline+['--max-new', '512'],
              '--authorized-device-window required'),
             ('pipeline513', common+pipeline+['--max-new', '513'],
              'bounded generation/context/deadline'),
             ('legacy129', common+['--max-new', '129'],
              'bounded generation/context/deadline'),
             ('context7', common+pipeline+['--max-new', '512', '--context', '7'],
              'bounded generation/context/deadline')]
    output = []
    env = dict(os.environ)
    env.pop('OWNRT_GSQ_FUSE_NORM', None)
    for name, argv, expected in cases:
        result = subprocess.run([str(args.binary.resolve()), *argv], env=env,
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and result.stderr.strip() == expected, (name, result)
        output.append(dict(name=name, argv=argv, returncode=result.returncode,
                           refusal=result.stderr.strip(), passed=True))
    assert not Path(common[-1]).exists()
    args.output.write_text(json.dumps(dict(passed=True, device_executed=False,
        binary=str(args.binary.resolve()),
        binary_sha256=hashlib.sha256(args.binary.read_bytes()).hexdigest(),
        cases=output), indent=2)+'\n')
    print('4 native parser cases passed; no device authorization supplied')


if __name__ == '__main__':
    main()
