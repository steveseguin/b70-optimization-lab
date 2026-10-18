"""Verify the separately bound legacy external symlinks."""
import json
from source_decision import O,P,ROOT,sha
def verify():
 row=json.loads((O/'inputs/external-source-bindings.json').read_text())
 for name,item in row.items():
  path=ROOT/name
  assert path.is_symlink() and str(path.readlink())==item['link'] and str(path.resolve())==item['resolved']
  assert sha(path)==item['sha256'],'external fixture bytes changed'
 return row
