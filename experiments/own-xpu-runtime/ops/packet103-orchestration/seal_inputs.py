"""Bind external CPU inputs without changing the oracle or weakening safe paths."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import orchestrate as o
import prepare_packet as packet

MANIFEST = o.P / 'oracle/results/suite-manifest.json'
SNAPSHOT = o.P / 'lineage-inputs/startup-suite-manifest.json'
RECEIPT = o.O / 'seal-inputs.json'
FIXTURES = ('nongemv-fixtures', 'p33-linked-fixtures', 'p49-qsa-fixtures',
            'p49b-expert-fixtures', 'p49c-fixtures', 'p49d-fixtures', 'k2-fixtures')


def prepare():
    from startup_receipt103 import verify as startup
    gate = startup()
    rows = []
    for name in FIXTURES:
        dest = o.P / 'build/gnu-host' / name
        source = (o.P.parent / 'packet56-draft-prefix/build/gnu-host' / name).resolve()
        expected = gate['sources'][o.pin_path(dest.parent) + '/' + name]
        assert o.sha(source) == o.sha(dest) == expected
        if dest.is_symlink():
            assert dest.resolve() == source
            temporary = dest.with_name(dest.name + '.local-link')
            os.link(source, temporary)
            os.replace(temporary, dest)  # Replaces only this packet's symlink.
        assert os.path.samefile(source, dest) and dest.resolve().is_relative_to(o.ROOT)
        rows.append(dict(path=str(dest.relative_to(o.ROOT)), source=str(source), sha256=expected))
    expected = gate['sources'][str(MANIFEST.relative_to(o.ROOT))]
    assert o.sha(MANIFEST) == expected
    if SNAPSHOT.exists():
        assert o.sha(SNAPSHOT) == expected
    else:
        SNAPSHOT.write_bytes(MANIFEST.read_bytes())
    size = sum(f.stat().st_size for f in (o.P/'build').rglob('*')
               if f.is_file() and not f.is_symlink())
    assert size < 300_000_000, size
    o.save(RECEIPT, dict(passed=True, device_executed=False,
        startup_sha256=o.sha(o.P/'startup103.json'), fixtures=rows,
        manifest=dict(original=str(MANIFEST.relative_to(o.ROOT)),
                      snapshot=str(SNAPSHOT.relative_to(o.ROOT)), sha256=expected),
        build_logical_bytes=size))
    verify()


def verify():
    from startup_receipt103 import verify as startup
    startup()  # Recheck executed inputs, including the unchanged external oracle.
    row = json.loads(RECEIPT.read_text())
    assert row['passed'] and row['device_executed'] is False
    assert row['startup_sha256'] == o.sha(o.P/'startup103.json')
    manifest = row['manifest']
    assert manifest['original'] == str(MANIFEST.relative_to(o.ROOT))
    assert manifest['snapshot'] == str(SNAPSHOT.relative_to(o.ROOT))
    assert o.sha(MANIFEST) == o.sha(SNAPSHOT) == manifest['sha256']
    assert {Path(r['path']).name for r in row['fixtures']} == set(FIXTURES)
    for item in row['fixtures']:
        path = o.ROOT/item['path']
        assert path.resolve().is_relative_to(o.ROOT) and not path.is_symlink()
        assert o.sha(path) == item['sha256']
    return row


def project(sources):
    """Only the manifest is represented by a snapshot in the generic screen seal."""
    sources = dict(sources)
    key = str(MANIFEST.relative_to(o.ROOT))
    expected = sources.pop(key)
    assert o.sha(MANIFEST) == o.sha(SNAPSHOT) == expected
    sources[str(SNAPSHOT.relative_to(o.ROOT))] = expected
    sources[str(RECEIPT.relative_to(o.ROOT))] = o.sha(RECEIPT)
    sources[str(Path(__file__).relative_to(o.ROOT))] = o.sha(Path(__file__))
    for name in sources:
        rel = Path(name)
        assert not rel.is_absolute() and '..' not in rel.parts
        assert (o.ROOT/rel).resolve().is_relative_to(o.ROOT), name
    return sources


def seal_view(choice, placement):
    verify()
    build, reports, sources = packet.proof()
    # Keep the original complete proof and receipt. Only the generic seal's
    # path representation changes; every proposal/launch verifies originals.
    with patch.object(packet, 'proof', return_value=(build, reports, project(sources))):
        return packet.seal_view(choice, placement)
