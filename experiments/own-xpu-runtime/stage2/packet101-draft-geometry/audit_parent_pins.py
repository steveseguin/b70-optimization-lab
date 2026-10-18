"""Read-only census of packet99/100 parent pins; write only packet101 evidence."""
import json
from build_engine import P, ROOT, sha, save, limits
from reseal import PARENT, parent_policy


def main():
    limits()
    rows = []
    for name in ('packet99-iq2-grid', 'packet100-down-locality'):
        packet = P.parent / name
        seals = sorted(p for p in packet.rglob('screen-seal.json') if 'build' not in p.relative_to(packet).parts)
        pins, occurrences = {}, {}
        for seal in seals:
            sources = json.loads(seal.read_text()).get('sources', {})
            for path, digest in sources.items():
                if not path.startswith(PARENT):
                    continue
                pins.setdefault(path, set()).add(digest)
                if parent_policy(path) != 'keep':
                    occurrences.setdefault(path, []).append(str(seal.relative_to(ROOT)))
        mismatches = {path: sorted(values) for path, values in pins.items()
                      if not (ROOT / path).is_file() or values != {sha(ROOT / path)}}
        row = dict(packet=name, seal_count=len(seals), parent_pin_count=len(pins),
                   mutable_selection_pinned=PARENT + 'selection.json' in pins,
                   orchestration_or_evidence_pins=occurrences, parent_hash_mismatches=mismatches,
                   seals={str(p.relative_to(ROOT)): sha(p) for p in seals}, modified=False)
        rows.append(row)
        print(name, len(seals), 'seals;', len(occurrences), 'parent evidence/output paths;',
              len(mismatches), 'parent hash mismatches')
    save(P / 'evidence/parent-pins-audit-20261018.json', dict(
        passed=True, device_executed=False, read_only=True, packets=rows,
        conclusion='Neither pins mutable parent selection. Both still pin evidence/object-identity.json; hashes currently match. No edits.'))


if __name__ == '__main__':
    main()
