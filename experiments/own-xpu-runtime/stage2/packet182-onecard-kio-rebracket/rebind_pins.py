#!/usr/bin/env python3
"""Packet182 copy step 2: re-bind in-packet pins of files the copy rewrote.

copy_packet.py rewrote packet176 identity strings in 10 text files (record in
lineage/packet182-copy.json). Packet-local manifests (for example
host-admission/seal.json) pinned the OLD bytes of some of them. For every pin
(pin_guard.extract_pins semantics, every JSON/text manifest outside lineage/,
frozen-inputs/ and build/) whose in-packet target this copy rewrote and whose
digest equals the pre-rewrite digest, the digest is replaced by the target's
current digest. A manifest changed this way is itself a rewritten file for
the next round (fixpoint). Every change is appended to lineage/packet182-copy.json
under "rebound". Pins to anything else are left alone (the pin guard and
final_checks.py judge them). CPU only.
"""
import hashlib, json, os, sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
sys.path.insert(0, str(ROOT / 'experiments/own-xpu-runtime/ops/lane-queue'))
import pin_guard  # noqa: E402

SKIP = {'lineage', 'frozen-inputs', 'build', '__pycache__'}


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def manifests():
    for f in sorted(P.rglob('*')):
        rel = f.relative_to(P)
        if f.is_symlink() or not f.is_file() or SKIP & set(rel.parts):
            continue
        if f.suffix in ('.json', '.sha256') or f.name == 'SHA256SUMS':
            yield f


def entries(path):
    raw = path.read_bytes()
    if path.suffix == '.json' or raw.lstrip().startswith((b'{', b'[')):
        row = json.loads(raw)
        direct = (pin_guard.is_pin_file(path) and isinstance(row, dict) and 'schema' not in row
                  and all(isinstance(v, str) for v in row.values()))
        return list(pin_guard.extract_pins(row, 'sources' if direct else ''))
    out = []
    for line in raw.decode().splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 64:
            out.append((parts[1].lstrip('*'), parts[0].lower()))
    return out


def main():
    record_path = P / 'lineage/packet182-copy.json'
    record = json.loads(record_path.read_text())
    rewritten = {str(P / rel): v['before_sha256'] for rel, v in record['rewritten'].items()}
    rebound = list(record.get('rebound', []))
    for _ in range(10):
        changes = 0
        for m in manifests():
            text = m.read_text()
            new = text
            for name, digest in entries(m):
                target = pin_path = pin_guard.pin_path(name, m, P, ROOT)
                if not (target.is_relative_to(P) and target.is_file()):
                    continue
                before = rewritten.get(str(target))
                if before is None or digest != before:
                    continue
                now = sha(target)
                if now == digest:
                    continue
                assert new.count(digest) >= 1, (m, name)
                new = new.replace(digest, now)
                rebound.append(dict(manifest=str(m.relative_to(P)), pin=name, old=digest, new=now))
            if new != text:
                old_sha = sha(m)
                m.write_text(new)
                rewritten.setdefault(str(m), old_sha)
                rel = str(m.relative_to(P))
                record['rewritten'].setdefault(rel, dict(before_sha256=old_sha, after_sha256=sha(m), reason='pin re-bind'))
                record['rewritten'][rel]['after_sha256'] = sha(m)
                changes += 1
        if not changes:
            break
    else:
        raise SystemExit('re-binding did not converge')
    record['rebound'] = rebound
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, rebound=len(rebound), manifests=sorted({r['manifest'] for r in rebound}))))


if __name__ == '__main__':
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    main()
