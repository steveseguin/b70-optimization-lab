#!/usr/bin/env python3
"""Packet58-onecard-cache23: private copy of packet182 (committed HEAD) with identity rewrites.

CPU only. No GPU, service, queue, packet182 or packet182c change. Run once from the repo root:

  nice -n 19 taskset -c 8-15,24-31 python3 -B <this> < /dev/null

- Source: `git archive <HEAD> experiments/own-xpu-runtime/stage2/packet182-onecard-kio-rebracket`
  (tracked files only; the working tree is never read).
- Build: NOT copied. The engine is rebuilt here (the arena/plan delta changes the entry TU);
  unchanged parent objects are restored by restore_build.py from their pinned originals.
- Text rewrites (outside lineage/, frozen-inputs/, native/ except native/k1_help.cpp): REWRITES.
- Dropped: packet182's evidence (except the 58c-kd test input), READY, seal receipt, screen
  evidence/proposals, the chain tooling, README/DO-NOT-REPEAT and the packet182-specific
  gate scripts that this packet replaces (DROP_EXACT).
"""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
STAGE = ROOT / 'experiments/own-xpu-runtime/stage2'
SRC_NAME = 'packet182-onecard-kio-rebracket'
DST_NAME = 'packet58-onecard-cache23'
SRC = STAGE / SRC_NAME
DST = STAGE / DST_NAME
REWRITES = [
    (SRC_NAME, DST_NAME),
    ('card0-182-v5-a', 'card0-58c23-v5-a'),
    ('proposed-p182-one-card-A.txt', 'proposed-p58cache23-one-card-A.txt'),
    ('packet182-one-card-v5-A', 'packet58cache23-one-card-v5-A'),
    ('packet182-smoke-A', 'packet58cache23-smoke-A'),
    ("name='packet182-'", "name='packet58cache23-'"),
    ('p182-', 'p58c23-'),
]
TEXT = {'.py', '.json', '.md', '.txt', '.tsv', '.jsonl', '.sh', '.snapshot', '.gitignore'}
NO_REWRITE_TOP = {'lineage', 'frozen-inputs', 'native'}
DROP_EXACT = {'READY-FOR-DEVICE.json', 'README.md', 'DO-NOT-REPEAT.md', 'screen/build-receipt.json',
              'copy_packet.py', 'rebind_pins.py', 'gates.py', 'package_rows.py', 'check_queue_rows.py', 'final_checks.py',
              'preparation182.py', 'inherited_gates.py', 'harness_tests.py', 'analyzer_gate.py', 'fill_price.py',
              'seal.py', 'plan_queue.py', 'test_kernelio_delta.py', 'build_k1_wrapper.py'}
DROP_PREFIX = ('screen/evidence/', 'screen/proposals/', 'chain/')
KEEP_EVIDENCE = ('evidence/58c-kd/',)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU stop: 27 GB root floor'
    assert not DST.exists(), DST_NAME + ' already exists; this copy runs once'
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True, stdin=subprocess.DEVNULL).strip()
    last = subprocess.check_output(['git', '-C', str(ROOT), 'log', '-1', '--format=%H', '--', str(SRC.relative_to(ROOT))],
                                   text=True, stdin=subprocess.DEVNULL).strip()
    raw = subprocess.run(['git', '-C', str(ROOT), 'archive', head, str(SRC.relative_to(ROOT))],
                         stdin=subprocess.DEVNULL, capture_output=True, check=True).stdout
    prefix = str(SRC.relative_to(ROOT)) + '/'
    copied, rewritten, dropped, symlinks = [], {}, [], []
    DST.mkdir()
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for m in tar.getmembers():
            if not m.name.startswith(prefix):
                continue
            rel = m.name[len(prefix):]
            if not rel or m.isdir():
                continue
            if rel in DROP_EXACT or rel.startswith(DROP_PREFIX) or (rel.startswith('evidence/') and not rel.startswith(KEEP_EVIDENCE)):
                dropped.append(rel)
                continue
            out = DST / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if m.issym():
                assert not os.path.isabs(m.linkname) and '..' not in Path(m.linkname).parts[1:], (rel, m.linkname)
                out.symlink_to(m.linkname)
                symlinks.append(dict(path=rel, target=m.linkname))
                continue
            data = tar.extractfile(m).read()
            top = Path(rel).parts[0]
            suffix = Path(rel).suffix or Path(rel).name
            if (suffix in TEXT and top not in NO_REWRITE_TOP) or rel == 'native/k1_help.cpp':
                text = data.decode()
                new = text
                for a, b in REWRITES:
                    new = new.replace(a, b)
                if new != text:
                    rewritten[rel] = dict(before_sha256=sha_bytes(data), after_sha256=sha_bytes(new.encode()))
                    data = new.encode()
            out.write_bytes(data)
            os.chmod(out, m.mode & 0o777)
            copied.append(rel)
    record = dict(
        schema='packet58cache23.copy-scope.v1',
        source=f'git archive {head} {prefix.rstrip("/")}',
        parent=dict(name=SRC_NAME, parent_relpath=str(SRC.relative_to(ROOT)), parent_commit=last),
        record_line=dict(name='packet182c-chain', parent_relpath='experiments/own-xpu-runtime/stage2/packet182c-chain',
                         note='packet182c is the record chain derived from packet182; same engine bytes 1b41fb4d...; its receipts are read in place, never copied'),
        working_tree_used=False,
        build_tree='not copied: engine rebuilt here; parent objects restored by restore_build.py from pinned originals',
        rewrites=[dict(old=a, new=b) for a, b in REWRITES],
        rewrite_scope='text files outside lineage/, frozen-inputs/, native/ (plus native/k1_help.cpp and .gitignore)',
        copied_files=len(copied), symlinks=symlinks, rewritten=rewritten, dropped=dropped)
    (DST / 'lineage').mkdir(exist_ok=True)
    (DST / 'lineage/packet58c23-copy.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, copied=len(copied), rewritten=len(rewritten), dropped=len(dropped), head=head)))


if __name__ == '__main__':
    main()
