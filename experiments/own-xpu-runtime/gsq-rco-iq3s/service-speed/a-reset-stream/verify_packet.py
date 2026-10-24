"""CPU/source-only verification. No compiler, subprocess, model or device API."""
from pathlib import Path
import hashlib
import json
import re
import unittest
import io

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
manifest = json.loads((HERE/'source-manifest.json').read_text())
receipt = json.loads((ROOT/'experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/evidence/native-build.json').read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def apply_in_memory(original, patch):
    old = original.splitlines(True); delta = patch.splitlines(True)
    result = []; cursor = 0; i = 2
    assert delta[0].startswith('--- a/') and delta[1].startswith('+++ b/')
    while i < len(delta):
        match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n', delta[i])
        assert match, delta[i]
        first, old_count, new_first, new_count = (int(x) if x is not None else 1 for x in match.groups())
        assert first - 1 >= cursor
        result += old[cursor:first-1]; cursor = first-1
        consumed = produced = 0; i += 1
        assert len(result) == new_first - 1
        while i < len(delta) and not delta[i].startswith('@@'):
            line = delta[i]; i += 1
            assert line[0] in ' +-'
            if line[0] in ' -':
                assert old[cursor] == line[1:]
                cursor += 1; consumed += 1
            if line[0] in ' +':
                result.append(line[1:]); produced += 1
        assert (consumed,produced) == (old_count,new_count)
    return ''.join(result + old[cursor:])

source_rows = []
for number, row in enumerate(manifest,1):
    original = ROOT/row['original']; copy = HERE/row['copy']
    assert sha(original) == row['original_sha256']
    assert sha(copy) == row['patched_sha256']
    expected = receipt['source_sha256'].get(str(original))
    assert expected == row['original_sha256'], str(original)
    patch = HERE/'patches'/f'{number:02d}-{original.name}.patch'
    assert apply_in_memory(original.read_text(), patch.read_text()) == copy.read_text()
    source_rows.append(dict(original=str(original),copy=str(copy),receipt_hash_matches=True,
                            patch_applies_exactly_in_memory=True))

dependencies = []
for obj in receipt['objects']:
    dep = Path(obj).with_suffix('.d')
    data = dep.read_text()
    affected = [r['original'] for r in manifest if str(ROOT/r['original']) in data]
    dependencies.append(dict(object=obj,exists=Path(obj).is_file(),dependency_file=str(dep),affected=affected))
assert all(r['exists'] for r in dependencies)
assert [Path(r['object']).name for r in dependencies if r['affected']] == ['entry.o']
assert len(next(r for r in dependencies if r['affected'])['affected']) == len(manifest)

# Follow literal includes from the copied entry to confirm all changed copies bind.
copied = {str(HERE/r['copy']) for r in manifest}
visited = set()
def visit(path):
    if str(path) in visited:return
    visited.add(str(path))
    for child in re.findall(r'^#include "([^"]+)"', path.read_text(), re.M):
        if child in copied:visit(Path(child))
visit(next(HERE/r['copy'] for r in manifest if r['original'].endswith('/entry.cpp')))
assert visited == copied
assets=[]
for name in ('rope.bf16','mtp-manifest.tsv'):
    p=ROOT/'experiments/own-xpu-runtime/stage2/packet136-record-bundle'/name
    assets.append(dict(path=str(p),exists=p.is_file(),bytes=p.stat().st_size,sha256=sha(p)))

suite = unittest.defaultTestLoader.discover(str(HERE),pattern='test_stream_parser.py')
log = io.StringIO()
result = unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(HERE/'python-tests.txt').write_text(log.getvalue())
assert result.wasSuccessful()
report = dict(passed=True,verification='source/bytes only; no build or device execution',
              source_checks=source_rows,object_dependencies=dependencies,
              include_binding_passed=True,historical_file_assets=assets,
              python_tests=result.testsRun,build_executed=False,device_executed=False)
(HERE/'source-check.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'{len(manifest)} original hashes match receipt; 7 patches apply exactly; '
      f'only entry.o affected; {result.testsRun} Python tests pass. No native build/run.')
