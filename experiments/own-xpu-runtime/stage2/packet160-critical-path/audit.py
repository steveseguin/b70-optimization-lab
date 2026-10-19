"""Read-only repository negative-result census; writes only packet160 evidence."""
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
    resource.setrlimit(resource.RLIMIT_AS, (2_000_000_000, 2_000_000_000))
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage(ROOT).free >= 27_000_000_000, '27 GB CPU stop'


def main():
    guard()
    paths = subprocess.check_output(['rg', '--files', '--hidden', '-g', 'DO-NOT-REPEAT.md', '-g', '!.git'], cwd=ROOT, text=True).splitlines()
    paths = sorted(p for p in paths if not p.startswith(str(P.relative_to(ROOT))+'/'))
    pattern = re.compile(r'66|79|106b?|120|126|132|145|149|151|153|156|draft|head|expert.parallel|provisional|early|depth.?2|pipeline|exchange|correction', re.I)
    manifest, matches = [], []
    for name in paths:
        raw = (ROOT/name).read_bytes()
        manifest.append(dict(path=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        for i, line in enumerate(raw.decode().splitlines(), 1):
            if pattern.search(line):
                matches.append(f'{name}:{i}:{line}')
    out = P/'evidence'
    out.mkdir(exist_ok=True)
    (out/'prior-audit.json').write_text(json.dumps(dict(files=manifest, count=len(paths), pattern=pattern.pattern), indent=2)+'\n')
    (out/'prior-matches.txt').write_text('\n'.join(matches)+'\n')
    print(json.dumps(dict(files=len(paths), matching_lines=len(matches), root_free_bytes=shutil.disk_usage(ROOT).free)))


if __name__ == '__main__':
    main()
