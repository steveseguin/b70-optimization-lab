"""Retain small, byte-exact existing receipts. CPU only; no model reads."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import subprocess

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
S = P.parent


def guard():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    resource.setrlimit(resource.RLIMIT_AS, (4_000_000_000, 4_000_000_000))


def main():
    guard()
    out = P/'evidence'
    out.mkdir(exist_ok=True)
    probe = S/'packet141-transfer-gap'
    run = probe/'evidence/probe-B-repair141c/run/incident-retrospective/rank0'
    sources = {name: run/name for name in (
        'p141-events.jsonl', 'p141-halves.jsonl', 'p141-controls.jsonl',
        'p141-state-hashes.jsonl', 'p141-complete.json', 'p141-touch-plan.jsonl')}
    sources.update({
        'probe-plan.json': probe/'probe-plan.json',
        'selection.json': probe/'selection.json',
        'record-intervals.csv': S/'packet160-critical-path/evidence/record-intervals.csv',
        'onecard-result.json': S/'packet58aj-onecard-resident/submission/prepared-a/result.json',
        'twocard-result.json': S/'packet136-record-bundle/submission/prepared-a/result.json',
    })
    pins = {}
    for name, source in sources.items():
        assert source.stat().st_size < 10_000_000
        raw = source.read_bytes()
        target = out/(name+'.gz')
        if target.exists():
            assert gzip.decompress(target.read_bytes()) == raw
        else:
            target.write_bytes(gzip.compress(raw, mtime=0))
        pins[name] = dict(source=str(source.relative_to(ROOT)), bytes=len(raw),
                          sha256=hashlib.sha256(raw).hexdigest(),
                          retained=target.name,
                          retained_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    # Every repository DO-NOT-REPEAT and every chronological own-runtime note,
    # including unrelated rows: retain the complete searched-file census.
    listing = subprocess.check_output(['rg', '--files', '-g', 'DO-NOT-REPEAT.md',
                                      '-g', '*own-runtime*.md', '-g', '*packet147*'],
                                     cwd=ROOT, stdin=subprocess.DEVNULL, text=True)
    paths = sorted({ROOT/x for x in listing.splitlines() if not (ROOT/x).is_relative_to(P)})
    paths += [S/'packet147-lever-synthesis/PLAN.md']
    pattern = re.compile(r'route.*(?:fus|epilogue)|router.*(?:fus|epilogue)|fus.*rout', re.I)
    census, matches = [], []
    for path in paths:
        raw = path.read_bytes()
        rel = str(path.relative_to(ROOT))
        census.append(dict(path=rel, sha256=hashlib.sha256(raw).hexdigest()))
        for number, line in enumerate(raw.decode().splitlines(), 1):
            if pattern.search(line):
                matches.append(f'{rel}:{number}:{line}')
    (out/'prior-matches.txt').write_text('\n'.join(matches)+'\n')
    (out/'prior-audit.json').write_text(json.dumps(dict(
        pattern=pattern.pattern, files=census, matches=len(matches)), indent=2)+'\n')
    (out/'input-pins.json').write_text(json.dumps(pins, indent=2)+'\n')
    print(f'Retained {len(pins)} exact inputs; searched {len(census)} prior files.')


if __name__ == '__main__':
    main()
