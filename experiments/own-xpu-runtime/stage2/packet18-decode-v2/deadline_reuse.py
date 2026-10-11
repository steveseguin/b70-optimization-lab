"""Narrow, hash-bound reuse of unchanged model gates after the watchdog repair."""
import hashlib
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def unchanged_or_model_neutral(path, original):
    path = path.resolve()
    if sha(path) == original: return True
    audit = json.loads((HERE / 'deadline-reuse.json').read_text())
    rel = str(path.relative_to(ROOT))
    canary = audit['isolated_canary']
    if rel == canary['path']:
        return original == canary['before_sha256'] and sha(path) == canary['after_sha256']
    change = audit['approved_model_neutral_edits'].get(rel)
    if not change or original != change['before_sha256'] or sha(path) != change['after_sha256']: return False
    text = path.read_text()
    for edit in change['edits']:
        assert edit['after'] and text.count(edit['after']) == 1, 'ambiguous approved edit'
        text = text.replace(edit['after'], edit['before'], 1)
    return hashlib.sha256(text.encode()).hexdigest() == original

def verify():
    audit = json.loads((HERE / 'deadline-reuse.json').read_text())
    for rel, digest in audit['original_sources'].items():
        # Python harness changes are rerun; numerical C++/data/build inputs cannot drift.
        if not rel.endswith('.py'):
            assert unchanged_or_model_neutral(ROOT / rel, digest), 'changed model input: ' + rel
    for rel, digest in audit['retained_receipts'].items():
        assert sha(HERE / rel) == digest, 'changed retained gate: ' + rel
    assert 'if(a.canary)return run_canary(a);' in (HERE/'main.cpp').read_text()
    return dict(audit_sha256=sha(HERE/'deadline-reuse.json'),
                original_host_sha256=audit['original_host_sha256'],
                retained_receipts=audit['retained_receipts'],
                scope='unchanged model path only; new canary/mini/unit/window checks run on rebuilt code')
