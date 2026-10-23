#!/usr/bin/env python3
"""Packet58-onecard-diet-engine: private copy of packet58-onecard-cache23 (committed HEAD) with identity rewrites.

CPU only. No GPU, service, queue or parent change. Run once from the repo root under nice 19 on the CPU-only cores.

- Source: `git archive HEAD experiments/own-xpu-runtime/stage2/packet58-onecard-cache23` (tracked files only).
- Build: NOT copied. The engine is rebuilt here (the diet kernel changes the p58ag_submit TU and the key the entry TU);
  unchanged parent objects are restored by restore_build.py from their pinned originals.
- Text rewrites outside lineage/, native/ and frozen-inputs/: REWRITES (identity strings).
- native/ and frozen-inputs/: ONLY the absolute include/#line prefix `stage2/packet58-onecard-cache23/` is rewritten to
  this packet (one header = one #pragma once identity, as packet58-onecard-cache23 did from packet176); bytes otherwise identical.
- lineage/: byte-for-byte (parent records), except cache23's own device-window receipts (lineage/window-*/) and the
  parent's K1/preparation snapshots that this packet regenerates.
- Dropped: cache23's evidence (except the 58c-kd K1 test input), READY, seal receipt, screen evidence/proposals,
  README/DO-NOT-REPEAT/RETENTION and the cache23 one-time delta generators / gates that this packet replaces.
"""
import hashlib, io, json, os, shutil, subprocess, tarfile
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
STAGE = ROOT / 'experiments/own-xpu-runtime/stage2'
SRC_NAME = 'packet58-onecard-cache23'
DST_NAME = 'packet58-onecard-diet-engine'
SRC = STAGE / SRC_NAME
DST = STAGE / DST_NAME
REWRITES = [
    (SRC_NAME, DST_NAME),
    ('card0-58c23-v5-a', 'card0-58de-v5-a'),
    ('proposed-p58-cache23-one-card-A.txt', 'proposed-p58-dietengine-one-card-A.txt'),
    ('packet58cache23-one-card-v5-A', 'packet58dietengine-one-card-v5-A'),
    ('packet58cache23-smoke-A', 'packet58dietengine-smoke-A'),
    ("name='packet58cache23-'", "name='packet58dietengine-'"),
    ('p58c23-', 'p58de-'),
]
PATH_OLD, PATH_NEW = 'stage2/' + SRC_NAME + '/', 'stage2/' + DST_NAME + '/'
TEXT = {'.py', '.json', '.md', '.txt', '.tsv', '.jsonl', '.sh', '.snapshot', '.gitignore', '.cpp', '.hpp', '.patch'}
NO_REWRITE_TOP = {'lineage'}
PATH_ONLY_TOP = {'native', 'frozen-inputs'}
DROP_EXACT = {'READY-FOR-DEVICE.json', 'README.md', 'DO-NOT-REPEAT.md', 'RETENTION.md', 'screen/build-receipt.json',
              'apply_cache23_delta.py', 'apply_harness_delta.py', 'apply_kernelio_delta.py', 'derive_plan.py', 'delta_test_receipt.py',
              'build_cache23.py', 'preparation_cache23.py', 'test_cache23_delta.py', 'analyzer_gate.py', 'harness_tests.py',
              'lineage/copy_packet.py'}
DROP_PREFIX = ('screen/evidence/', 'screen/proposals/', 'lineage/window-')
KEEP_EVIDENCE = ('evidence/58c-kd/',)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU stop: 27 GB root floor'
    assert not DST.exists(), DST_NAME + ' already exists; this copy runs once'
    assert not subprocess.check_output(['git', '-C', str(ROOT), 'status', '--short', '--', str(SRC.relative_to(ROOT))], text=True, stdin=subprocess.DEVNULL).strip(), 'parent tree is not clean at HEAD'
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True, stdin=subprocess.DEVNULL).strip()
    last = subprocess.check_output(['git', '-C', str(ROOT), 'log', '-1', '--format=%H', '--', str(SRC.relative_to(ROOT))], text=True, stdin=subprocess.DEVNULL).strip()
    raw = subprocess.run(['git', '-C', str(ROOT), 'archive', head, str(SRC.relative_to(ROOT))], stdin=subprocess.DEVNULL, capture_output=True, check=True).stdout
    prefix = str(SRC.relative_to(ROOT)) + '/'
    copied, rewritten, path_rewritten, dropped, symlinks = [], {}, {}, [], []
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
            if suffix in TEXT and top not in NO_REWRITE_TOP:
                try:
                    text = data.decode()
                except UnicodeDecodeError:
                    text = None
                if text is not None:
                    new = text
                    if top in PATH_ONLY_TOP:
                        n = new.count(PATH_OLD)
                        new = new.replace(PATH_OLD, PATH_NEW)
                        if n:
                            path_rewritten[rel] = n
                    else:
                        for a, b in REWRITES:
                            new = new.replace(a, b)
                    if new != text:
                        rewritten[rel] = dict(before_sha256=sha_bytes(data), after_sha256=sha_bytes(new.encode()))
                        data = new.encode()
            out.write_bytes(data)
            os.chmod(out, m.mode & 0o777)
            copied.append(rel)
    record = dict(
        schema='packet58dietengine.copy-scope.v1',
        source=f'git archive {head} {prefix.rstrip("/")}',
        parent=dict(name=SRC_NAME, parent_relpath=str(SRC.relative_to(ROOT)), parent_commit=last),
        record_line=dict(name='packet58-onecard-cache23-chain', parent_relpath='experiments/own-xpu-runtime/stage2/packet58-onecard-cache23-chain',
                         note='the 36.602512 tok/s record chain bound the cache23 engine 083e3853... byte for byte; its receipts are read in place, never copied'),
        working_tree_used=False,
        build_tree='not copied: engine rebuilt here (p58ag_submit + entry TUs); unchanged parent objects restored by restore_build.py from pinned originals',
        rewrites=[dict(old=a, new=b) for a, b in REWRITES],
        rewrite_scope='text files outside lineage/; native/ and frozen-inputs/ carry only the absolute path prefix rewrite',
        path_rewrite=dict(old=PATH_OLD, new=PATH_NEW, files=path_rewritten, occurrences=sum(path_rewritten.values())),
        copied_files=len(copied), symlinks=symlinks, rewritten=rewritten, dropped=dropped)
    (DST / 'lineage').mkdir(exist_ok=True)
    (DST / 'lineage/packet58de-copy.json').write_text(json.dumps(record, indent=2) + '\n')
    shutil.copy2(__file__, DST / 'lineage/copy_packet.py')
    print(json.dumps(dict(passed=True, copied=len(copied), rewritten=len(rewritten), path_files=len(path_rewritten), path_occurrences=sum(path_rewritten.values()), dropped=len(dropped), head=head)))


if __name__ == '__main__':
    main()
