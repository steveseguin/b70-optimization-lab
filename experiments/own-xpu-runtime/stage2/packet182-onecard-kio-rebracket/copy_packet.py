#!/usr/bin/env python3
"""Packet182: private copy of packet176 (committed HEAD) with identity rewrites.

CPU only. No GPU, service, queue or packet176 change. Run once from the repo root:

  nice -n 19 taskset -c 8-15,24-31 python3 -B <this> < /dev/null

- Source: `git archive <HEAD> experiments/own-xpu-runtime/stage2/packet176-onecard-kernelio`
  (tracked files only; the working tree is not read except for build/, which Git ignores).
- Build: packet176's ignored build/ tree copied byte for byte (hash-checked against
  packet176's sealed artifacts). The K1 wrapper build/device/p58-cache-fixtures is NOT
  copied; it is rebuilt by build_k1_wrapper.py so it execs this packet's own core.
- Text rewrites (outside lineage/, frozen-inputs/, native/ except native/k1_help.cpp):
  see REWRITES. Pins whose in-packet target this copy rewrote are re-bound to the new
  bytes (old digest kept in lineage/packet182-copy.json).
- Dropped: packet176's evidence (except the 58c-kd test input), READY, seal receipt,
  screen evidence/proposals, finalize/proposal_gates (replaced by packet182 scripts),
  README/DO-NOT-REPEAT (rewritten for packet182).
"""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
STAGE = ROOT / 'experiments/own-xpu-runtime/stage2'
SRC_NAME = 'packet176-onecard-kernelio'
DST_NAME = 'packet182-onecard-kio-rebracket'
SRC = STAGE / SRC_NAME
DST = STAGE / DST_NAME
REWRITES = [
    (SRC_NAME, DST_NAME),
    ('card0-176-v5-a', 'card0-182-v5-a'),
    ('proposed-p176-v5-A.txt', 'proposed-p182-one-card-A.txt'),
    ('packet176-v5-A', 'packet182-one-card-v5-A'),
    ('packet58-onecard-176-a', 'packet58-onecard-182-a'),
    ('card0-176-a', 'card0-182-a'),
]
TEXT = {'.py', '.json', '.md', '.txt', '.tsv', '.jsonl', '.sh', '.snapshot'}
NO_REWRITE_TOP = {'lineage', 'frozen-inputs', 'native'}
DROP_EXACT = {'READY-FOR-DEVICE.json', 'finalize.py', 'proposal_gates.py', 'README.md', 'DO-NOT-REPEAT.md',
              'screen/build-receipt.json'}
DROP_PREFIX = ('screen/evidence/', 'screen/proposals/')
KEEP_EVIDENCE = ('evidence/58c-kd/',)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU stop: 27 GB root floor'
    assert not DST.exists(), 'packet182 already exists; this copy runs once'
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
            if (Path(rel).suffix in TEXT and top not in NO_REWRITE_TOP) or rel == 'native/k1_help.cpp':
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
    # Ignored build tree (binaries, inherited objects, preparation probe). K1 wrapper rebuilt separately.
    build = []
    sealed = json.loads(subprocess.run(['git', '-C', str(ROOT), 'show', f'{head}:{prefix}screen/build-receipt.json'],
                                       stdin=subprocess.DEVNULL, capture_output=True, check=True, text=True).stdout)
    for f in sorted((SRC / 'build').rglob('*')):
        if f.is_symlink() or not f.is_file():
            assert not f.is_symlink(), 'symlink in packet176 build: ' + str(f)
            continue
        rel = f.relative_to(SRC)
        if str(rel) == 'build/device/p58-cache-fixtures':
            dropped.append(str(rel) + ' (K1 wrapper: rebuilt for this packet path)')
            continue
        dest = DST / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        assert sha(dest) == sha(f)
        build.append(dict(path=str(rel), sha256=sha(dest)))
    for name, digest in sealed['artifacts'].items():
        if name == 'build/device/p58-cache-fixtures':
            continue
        assert sha(DST / name) == digest, 'sealed packet176 artifact differs: ' + name
    record = dict(
        schema='packet182.copy-scope.v1',
        source=f'git archive {head} {prefix.rstrip("/")}',
        parent=dict(name=SRC_NAME, parent_relpath=str(SRC.relative_to(ROOT)), parent_commit=last),
        working_tree_used='build/ only (ignored by Git): binaries, inherited objects, preparation probe',
        rewrites=[dict(old=a, new=b) for a, b in REWRITES],
        rewrite_scope='text files outside lineage/, frozen-inputs/, native/ (plus native/k1_help.cpp)',
        copied_files=len(copied), symlinks=symlinks, rewritten=rewritten, dropped=dropped, build_files=build,
        packet176_sealed_artifacts=dict(sealed['artifacts']),
        k1_wrapper='rebuilt (build_k1_wrapper.py): packet176 wrapper execs packet176 core by absolute path',
        runtime_read_outside_packet=dict(
            path='experiments/own-xpu-runtime/stage2/packet176-onecard-kernelio/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/rope.bf16',
            reason='the unchanged device binary opens fs::path(__FILE__).parent_path()/"rope.bf16"; __FILE__ was compiled in packet176',
            parent_digest=sha(SRC / 'frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/rope.bf16'),
            tracked=True, enforced_by='the binary checks the 4,194,304-byte table against rope_constants::sha256 at load and refuses'))
    (DST / 'lineage').mkdir(exist_ok=True)
    (DST / 'lineage/packet182-copy.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, copied=len(copied), rewritten=len(rewritten), dropped=len(dropped), build=len(build), head=head)))


if __name__ == '__main__':
    main()
