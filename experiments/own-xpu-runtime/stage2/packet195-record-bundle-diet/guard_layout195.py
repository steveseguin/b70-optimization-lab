"""Move inherited provenance out of packet195's guarded closure (packet143 layout), CPU only, idempotent.

The live lane-queue pin guard (ops/lane-queue/pin_guard.py) walks this packet's metadata and refuses
any hash pin on a mutable file outside the packet. Packet155's copied metadata carried 3,925 such pins,
all historical provenance. Packet143 (bundle 8, the 58.80 record) solved the same inheritance by keeping
provenance inside the packet under lineage-inputs/. This script applies that layout, byte for byte:

1. parent-snapshot/, calibration/, prefix-calibration/ -> lineage-inputs/<same>, with a relative
   symlink at the old path (packet143 has the same three symlinks), so readers keep their paths;
2. lineage-inputs/packet194-build.json (packet194's build receipt, provenance of the reused exp-diet engines;
   place_diet.py writes it there directly);
3. chain-binding.json `parent` -> lineage-inputs/packet75-chain-binding.json (byte copy, same sha256);
4. input-fixtures.json `archive` -> lineage-inputs/fixture-archive.tar.gz (hard link of the same inode
   packet143 links, no new disk bytes);
5. storage-measurements.json window `receipt`s -> lineage-inputs/packet136-chain-windows/<W>/window.json
   (byte copies of packet136's chain window receipts, same sha256);
6. dependency-pins.json: drop the four shared scripts the chain never imports (screen/seal.py,
   scripts/{promotion_evidence,receipt_qualification,submit_localmaxxing_results}.py). Their pinned
   bytes are vendored in lineage-inputs/dependencies/ (equal to the dropped digests, checked here).
   The frozen screen/v4-lanes wrapper pins stay. The submission step uses the live shared scripts and
   is rehearsed separately (ops/packet195-orchestration/submission_rehearsal.py).

7. hard links (no new disk bytes; packet143 layout) so every relative seal name resolves inside the packet
   where the guard resolves it: <packet>/{device,gnu-host}/<artifact> for build-receipt artifacts_sha256
   (names are build/-relative; the guard resolves them against the packet root), each selection view's
   build/{device,gnu-host}/own-rt-iq3 (screen-seal artifacts are view-relative), and
   lineage-inputs/link-targets/build/fusion-fixtures/<name> for the inherited fixture identities;
   chain_seal.py keys fixture_inputs_sha256 by those paths and oracle_inputs_sha256 by the packet49
   oracle paths (the sealed digests are unchanged).

Every moved or copied byte is verified against the digest it replaces; the receipt is
lineage/packet195-guard-layout.json.
"""
import hashlib, json, os, shutil
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
STAGE = P.parent
L = P / 'lineage-inputs'
DROPPED = ('experiments/own-xpu-runtime/stage2/screen/seal.py', 'scripts/promotion_evidence.py',
           'scripts/receipt_qualification.py', 'scripts/submit_localmaxxing_results.py')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def tree(root):
    return {str(f.relative_to(root)): sha(f) for f in sorted(root.rglob('*')) if f.is_file() and not f.is_symlink()}


def save(path, row):
    path.write_text(json.dumps(row, indent=2) + '\n')


def move_dir(name, receipt):
    old, new = P / name, L / name
    if old.is_symlink():
        assert os.readlink(old) == 'lineage-inputs/' + name and new.is_dir(), name
        receipt[name] = dict(state='already moved', files=len(tree(new)))
        return
    assert old.is_dir() and not new.exists(), name
    before = tree(old)
    shutil.move(str(old), str(new))
    os.symlink('lineage-inputs/' + name, old)
    assert tree(new) == before and tree(old.resolve()) == before, name
    receipt[name] = dict(state='moved', files=len(before), symlink='lineage-inputs/' + name,
                         tree_sha256=hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest())


def hard_link(src, dst):
    src = Path(src).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_ino != src.stat().st_ino:
        dst.unlink()
    if not dst.exists():
        os.link(src, dst)
    assert dst.stat().st_ino == src.stat().st_ino and not dst.is_symlink(), dst
    return sha(dst)


def link_artifacts():
    seal = json.loads((P / 'lineage-inputs/packet136-chain-seal.json').read_text())
    out = dict(artifacts={}, views={}, fixtures=0)
    names = set(seal['artifacts_sha256']) | {'device/own-rt-iq3', 'gnu-host/own-rt-iq3'}
    for name in sorted(names):
        out['artifacts'][name] = hard_link(P / 'build' / name, P / name)
    for view in sorted((P / 'selections').iterdir()):
        for mode in ('device', 'gnu-host'):
            rel = 'build/' + mode + '/own-rt-iq3'
            out['views'][view.name + '/' + rel] = hard_link(P / rel, view / rel)
    for name, digest in seal['fixture_inputs_sha256'].items():
        assert hard_link(P / 'build/fusion-fixtures' / name, L / 'link-targets/build/fusion-fixtures' / name) == digest, name
        out['fixtures'] += 1
    return out


def main():
    receipt = dict(schema='packet195.guard-layout.v1', device_executed=False, precedent='packet143-record-bundle lineage-inputs layout')
    moves = {}
    for name in ('parent-snapshot', 'calibration', 'prefix-calibration'):
        move_dir(name, moves)
    receipt['directories'] = moves

    new = L / 'packet194-build.json'
    assert sha(new) == sha(STAGE / 'packet194-expert-diet-engine/v5/evidence/build.json')
    receipt['packet194_build'] = dict(path=str(new.relative_to(P)), origin='stage2/packet194-expert-diet-engine/v5/evidence/build.json', digest=sha(new))

    binding = json.loads((P / 'chain-binding.json').read_text())
    target = L / 'packet75-chain-binding.json'
    origin = STAGE / 'packet75-record-bundle/chain-binding.json'
    if not target.exists():
        shutil.copy2(origin, target)
    assert sha(target) == binding['parent_sha256'], 'packet75 chain binding bytes differ from the sealed digest'
    binding['parent'] = str(target.relative_to(ROOT))
    save(P / 'chain-binding.json', binding)
    receipt['chain_binding'] = dict(parent=binding['parent'], digest=binding['parent_sha256'], origin=str(origin.relative_to(ROOT)))

    fixtures = json.loads((P / 'input-fixtures.json').read_text())
    archive = L / 'fixture-archive.tar.gz'
    origin = STAGE / 'disk-cleanup-20261017-1510/archives/packet21-fused--fusion-fixtures.tar.gz'
    if not archive.exists():
        os.link(origin, archive)
    assert archive.stat().st_ino == origin.stat().st_ino and sha(archive) == fixtures['archive_sha256']
    fixtures['archive'] = str(archive)
    for name, item in fixtures['files'].items():  # packet143 form: each identity names its packet-local link target
        item['path'] = str((L / 'link-targets/build/fusion-fixtures' / name).relative_to(ROOT))
    save(P / 'input-fixtures.json', fixtures)
    receipt['fixture_archive'] = dict(path=str(archive.relative_to(P)), hard_link_of=str(origin.relative_to(ROOT)), inode=archive.stat().st_ino,
                                      digest=fixtures['archive_sha256'], new_disk_bytes=0)

    storage = json.loads((P / 'storage-measurements.json').read_text())
    copied = {}
    for name, window in storage['windows'].items():
        source = ROOT / window['receipt']
        if 'lineage-inputs' not in source.parts:
            dst = L / 'packet136-chain-windows' / name / 'window.json'
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(source, dst)
            window['receipt'] = str(dst.relative_to(ROOT))
        assert sha(ROOT / window['receipt']) == window['receipt_sha256'], name
        copied[name] = window['receipt']
    save(P / 'storage-measurements.json', storage)
    receipt['storage_receipts'] = copied

    pins = json.loads((P / 'dependency-pins.json').read_text())
    dropped = {}
    for name in DROPPED:
        if name in pins:
            dropped[name] = pins.pop(name)
    vendored = {name: sha(L / 'dependencies' / Path(name).name) for name in DROPPED}
    previous = json.loads((P / 'lineage/packet195-guard-layout.json').read_text())['dependency_pins_dropped'] if (P / 'lineage/packet195-guard-layout.json').exists() else {}
    for name in DROPPED:
        assert vendored[name] == dropped.get(name, previous.get(name)), 'vendored copy differs from the dropped pin: ' + name
    assert all('/screen/v4-lanes/' in k for k in pins), 'only frozen v4 wrapper pins may remain'
    save(P / 'dependency-pins.json', pins)
    receipt['dependency_pins_dropped'] = dropped or previous
    receipt['dependency_pins_vendored'] = {k: 'lineage-inputs/dependencies/' + Path(k).name for k in DROPPED}
    receipt['dependency_pins_kept'] = len(pins)
    receipt['hard_links'] = link_artifacts()
    for name, item in fixtures['files'].items():
        assert sha(ROOT / item['path']) == item['sha256'] and (ROOT / item['path']).stat().st_size == item['bytes'], name
    save(P / 'lineage/packet195-guard-layout.json', receipt)
    print('guard layout applied:', ', '.join(f'{k}={v["state"]}' for k, v in moves.items()), '| storage receipts', len(copied),
          '| dependency pins kept', len(pins))


if __name__ == '__main__':
    main()
