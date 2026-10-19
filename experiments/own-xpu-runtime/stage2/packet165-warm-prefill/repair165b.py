"""Retain exact native-test source bytes locally; never compile or launch."""
import json
import shutil
from pathlib import Path
from build_engine import P, ROOT, sha, save, limits

limits()
for name in ('one-card', 'two-card'):
    receipt = P / name / 'evidence/native-sequence.json'
    original = P / name / 'lineage/packet165b-native-sequence-original.json'
    if not original.exists():
        shutil.copyfile(receipt, original)
    row = json.loads(original.read_text())
    pins = {}
    for source, digest in row['sources_sha256'].items():
        source = Path(source)
        assert source.suffix in ('.py', '.cpp', '.hpp', '.h', '.inc'), source
        assert sha(source) == digest, source
        if not source.is_relative_to(P):
            target = P / name / 'lineage/packet165b-sources' / (digest + '-' + source.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        else:
            target = source
        assert sha(target) == digest
        pins[str(target.relative_to(ROOT))] = digest
    row['sources_sha256'] = pins
    row['source_retention'] = {
        'scope': 'Exact source snapshots only; original commands and results unchanged; no rerun or compile.',
        'path': str(original.relative_to(ROOT)),
        'sha256': sha(original),
    }
    save(receipt, row)
    print(name, len(pins), 'native source pins retained')
