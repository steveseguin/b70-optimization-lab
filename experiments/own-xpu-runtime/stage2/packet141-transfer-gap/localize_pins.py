"""Snapshot exact compiled source bytes; retain original compile commands as provenance.

Run after a build and before sealing. This does not claim recompilation from the
snapshot paths: source bytes are checked against the compiler receipt first.
Parent ELF objects remain immutable inputs; historical receipts stay archived.
"""
import gzip
import json
from pathlib import Path
import resource
from build_engine import P, ROOT, sha, save, limits


def main():
    limits()
    evidence = P / 'evidence/repair141b'
    mapping_path = P / 'compiled-source-snapshots.json'
    mapping = json.loads(mapping_path.read_text()) if mapping_path.exists() else dict(files=[])
    for receipt in (P / 'build-receipt.json', P / 'evidence/full-shape.json'):
        row = json.loads(receipt.read_text())
        for name, digest in list(row['sources'].items()):
            source = ROOT / name
            if source.is_relative_to(P):
                continue
            if source.suffix in ('.o', '.a', '.so'):
                assert sha(source) == digest
                # Resolve inherited link chains to the actual immutable ELF.
                del row['sources'][name]
                row['sources'][str(source.resolve().relative_to(ROOT))] = digest
                continue
            assert sha(source) == digest, 'compiled source changed: ' + name
            dest = P / 'compiled-sources' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source.read_bytes())
            assert sha(dest) == digest
            del row['sources'][name]
            row['sources'][str(dest.relative_to(ROOT))] = digest
            item = dict(compiled_from=name, snapshot_file=str(dest.relative_to(ROOT)), snapshot_file_sha256=digest)
            if item not in mapping['files']: mapping['files'].append(item)
        row['source_path_policy'] = 'Exact compiled bytes snapshotted locally after build; original commands retained, no recompilation implied.'
        save(receipt, row)
    save(mapping_path, mapping)
    # Three small immutable input files were links to an unfrozen shared tree.
    # Preserve their exact bytes locally, without changing suite identity.
    for name in ('identity.tsv', 'plan.tsv', 'vocab.bin'):
        path = P / 'inputs/incident-retrospective' / name
        if path.is_symlink():
            raw = path.read_bytes(); digest = sha(path)
            path.unlink(); path.write_bytes(raw)
            assert sha(path) == digest
    # The generic pin reader interprets the suite's basename hash keys relative
    # to the suite file. These packet-local aliases bind the same input bytes;
    # input_gate still validates the full bundle in its original location.
    for name in ('identity.tsv', 'plan.tsv', 'vocab.bin', 'input.json', 'tokens.txt'):
        alias = P / name
        target = Path('inputs/incident-retrospective') / name
        if not alias.exists(): alias.symlink_to(target)
        assert alias.is_symlink() and alias.readlink() == target
    # The unchanged oracle result is an explicit authority binding, not an
    # executable source dependency and not a new oracle qualification.
    suite = json.loads((P / 'suite.snapshot.json').read_text())
    binding = json.loads((P / 'oracle-binding.json').read_text())
    for entry in suite['prompts']:
        assert sha(ROOT / entry['reference']) == entry['reference_sha256']
        binding['files_sha256'][entry['reference']] = entry['reference_sha256']
    save(P / 'oracle-binding.json', binding)
    proposal = ROOT / 'experiments/own-xpu-runtime/ops/lane-queue/proposed-p141-probe-B.txt'
    (P / 'proposal.snapshot.txt').write_bytes(proposal.read_bytes())
    # Historical metadata must not be confused with a current executable seal.
    # Verify every original byte before retiring the redundant uncompressed copy.
    for name in ('original-build-receipt.json', 'original-packet-seal.json', 'original-READY-FOR-DEVICE.json'):
        path = evidence / name
        if path.exists():
            raw = path.read_bytes(); archived = path.with_suffix('.json.gz')
            archived.write_bytes(gzip.compress(raw, mtime=0))
            assert gzip.decompress(archived.read_bytes()) == raw
            path.unlink()
    old_ready = P / 'READY-FOR-DEVICE.json'
    if old_ready.exists():
        assert old_ready.read_bytes() == gzip.decompress((evidence / 'original-READY-FOR-DEVICE.json.gz').read_bytes())
        old_ready.unlink()  # withdraw stale readiness; replacement is the last write
    print('Compiled-source snapshots, local input bytes, unchanged oracle binding and proposal snapshot PASS')


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    main()
