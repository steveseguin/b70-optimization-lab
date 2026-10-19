"""Read-only source census; no model access or runtime imports."""
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess

P = Path(__file__).resolve().parent
ROOT = P.parents[3]


def guard():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    resource.setrlimit(resource.RLIMIT_AS, (4_000_000_000, 4_000_000_000))
    assert shutil.disk_usage(ROOT).free >= 27_000_000_000, 'CPU storage stop: 27 GB'


def main():
    guard()
    paths = subprocess.check_output(['rg', '--files', '-g', '*DO-NOT-REPEAT*'],
                                    cwd=ROOT, stdin=subprocess.DEVNULL).decode().splitlines()
    records, matches = [], []
    for name in sorted(paths):
        raw = (ROOT/name).read_bytes()
        records.append(dict(path=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        for n, line in enumerate(raw.decode().splitlines(), 1):
            if re.search(r'argmax|head', line, re.I):
                matches.append(f'{name}:{n}:{line}')
    (P/'evidence').mkdir(exist_ok=True)
    (P/'evidence/prior-audit.json').write_text(json.dumps(records, indent=2)+'\n')
    (P/'evidence/prior-matches.txt').write_text('\n'.join(matches)+'\n')
    print(json.dumps(dict(files=len(records), matching_lines=len(matches))))


if __name__ == '__main__':
    main()
